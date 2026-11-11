from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_NAME: str = "SmartSpend API"
    JWT_SECRET_KEY: str
    DEMO_POS_ENABLED: bool = False
    APP_ENV: Literal["development", "test", "production"] = "development"
    RATE_LIMIT_ENABLED: bool = False
    REDIS_URL: str | None = None
    RATE_LIMIT_PREFIX: str = "smartspend:limits"

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def validate_environment(self):
        if self.APP_ENV == "production":
            if not self.RATE_LIMIT_ENABLED or not self.REDIS_URL:
                raise ValueError(
                    "Production requires Redis rate limiting"
                )

            if self.DEMO_POS_ENABLED:
                raise ValueError(
                    "Demo POS cannot be enabled in production"
                )

            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "Production JWT secret must be at least 32 characters"
                )

        return self


settings = Settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
