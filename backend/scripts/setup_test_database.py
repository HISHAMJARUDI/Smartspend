import os
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.database import settings


TEST_DATABASE = "smartspend_test"

source_url = make_url(settings.DATABASE_URL)

if source_url.get_backend_name() != "postgresql":
    raise SystemExit("Expected a PostgreSQL database")

if source_url.database == TEST_DATABASE:
    test_url = source_url
else:
    if source_url.database != "smartspend_db":
        raise SystemExit(
            "Unexpected source database. Setup cancelled."
        )

    test_url = source_url.set(database=TEST_DATABASE)

test_engine = create_engine(
    test_url,
    pool_pre_ping=True,
)

try:
    with test_engine.connect() as connection:
        actual_database = connection.scalar(
            text("SELECT current_database()")
        )

        if actual_database != TEST_DATABASE:
            raise SystemExit(
                "Database safety check failed."
            )

    print("Verified target: smartspend_test")
    print("Applying Alembic migrations...")

    child_env = os.environ.copy()
    child_env["DATABASE_URL"] = test_url.render_as_string(
        hide_password=False
    )

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=child_env,
    )

    print("Test database migrations completed.")

finally:
    test_engine.dispose()
