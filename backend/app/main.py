from app.api.terminal_management import router as terminal_management_router
from app.api.audit import router as audit_router
from app.api.cards import router as cards_router
from app.api.parent_dashboard import router as parent_dashboard_router
from app.api.wallets import router as wallets_router
from app.api.pos import router as pos_router
from app.api.students import router as students_router
from app.api.parents import router as parents_router
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.core.rate_limiter import (
    check_limit,
    terminal_identity,
    RateLimitUnavailable,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine, settings
from app.api.auth import router as auth_router
from app.api.schools import router as schools_router


app = FastAPI(
    title=settings.APP_NAME,
    description="SmartSpend Closed-Loop School Payment Platform",
    version="1.0.0",
)

@app.middleware("http")
async def smartspend_rate_limit(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    if request.method != "POST":
        return await call_next(request)

    path = request.url.path

    # Never trust a user-supplied X-Forwarded-For header here.
    # Configure trusted reverse proxies at deployment time.
    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    policies = []

    if path == "/auth/login":
        policies.append(("login", client_ip))

    elif path == "/pos/purchases":
        policies.append(("pos_ip", client_ip))

        terminal_id = terminal_identity(
            request.headers.get("X-Terminal-Key")
        )

        if terminal_id is not None:
            policies.append((
                "pos_terminal",
                terminal_id,
            ))

    elif path.startswith("/admin/terminals/"):
        if path.endswith(("/rotate", "/revoke")):
            policies.append((
                "terminal_admin",
                client_ip,
            ))

    try:
        for policy, identity in policies:
            allowed, retry_after = check_limit(
                policy,
                identity,
            )

            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests"
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "Cache-Control": "no-store",
                    },
                )

    except RateLimitUnavailable:
        # Protected operations fail closed if Redis is down.
        if policies:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Request protection temporarily "
                        "unavailable"
                    )
                },
                headers={"Cache-Control": "no-store"},
            )

    return await call_next(request)


# Register all routers before defining regular routes.
app.include_router(auth_router)
app.include_router(schools_router)


@app.get("/")
def home():
    return {
        "application": "SmartSpend",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "PostgreSQL",
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

app.include_router(parents_router)

app.include_router(students_router)

app.include_router(pos_router)

app.include_router(wallets_router)

app.include_router(parent_dashboard_router)

app.include_router(cards_router)

app.include_router(audit_router)

app.include_router(terminal_management_router)
