"""Environment configuration, validated loudly at import time (fail fast at startup)."""

import os
from dataclasses import dataclass

MIN_JWT_SECRET_BYTES = 32


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"missing required environment variable {name}")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    cors_origins: tuple[str, ...]
    access_token_minutes: int = 30
    refresh_token_days: int = 14


def load_settings() -> Settings:
    database_url = _require("DATABASE_URL")
    if not database_url.startswith("postgresql+psycopg://"):
        raise ConfigError("DATABASE_URL must use the postgresql+psycopg:// driver")
    jwt_secret = _require("JWT_SECRET")
    if len(jwt_secret.encode()) < MIN_JWT_SECRET_BYTES:
        raise ConfigError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes")
    origins = tuple(o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip())
    if "*" in origins:
        raise ConfigError("CORS_ORIGINS must be an explicit allowlist, never '*'")
    return Settings(database_url=database_url, jwt_secret=jwt_secret, cors_origins=origins)


settings = load_settings()
