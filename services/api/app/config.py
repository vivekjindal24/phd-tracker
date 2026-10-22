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
class Smtp:
    host: str
    port: int
    user: str
    password: str
    mail_from: str


SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM")
DEFAULT_MAX_UPLOAD_MB = 100


@dataclass(frozen=True)
class S3:
    endpoint: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    max_upload_bytes: int


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    cors_origins: tuple[str, ...]
    app_base_url: str
    smtp: Smtp | None
    s3: S3
    access_token_minutes: int = 30
    refresh_token_days: int = 14


def _load_smtp() -> Smtp | None:
    """All-or-nothing: none set = email off (recorded per notification); some set = error."""
    values = {name: os.environ.get(name, "").strip() for name in SMTP_VARS}
    filled = [name for name, value in values.items() if value]
    if not filled:
        return None
    missing = [name for name in SMTP_VARS if not values[name]]
    if missing:
        raise ConfigError("email is partly configured; also set " + ", ".join(missing))
    if not values["SMTP_PORT"].isdigit():
        raise ConfigError("SMTP_PORT must be a number")
    return Smtp(
        host=values["SMTP_HOST"],
        port=int(values["SMTP_PORT"]),
        user=values["SMTP_USER"],
        password=values["SMTP_PASSWORD"],
        mail_from=values["MAIL_FROM"],
    )


def _load_s3() -> S3:
    max_mb = os.environ.get("MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB)).strip()
    if not max_mb.isdigit() or not 1 <= int(max_mb) <= 5000:
        raise ConfigError("MAX_UPLOAD_MB must be a whole number between 1 and 5000")
    endpoint = _require("S3_ENDPOINT").rstrip("/")
    if not endpoint.startswith(("https://", "http://")):
        raise ConfigError("S3_ENDPOINT must be an http(s) URL")
    return S3(
        endpoint=endpoint,
        region=os.environ.get("S3_REGION", "auto").strip() or "auto",
        bucket=_require("S3_BUCKET"),
        access_key_id=_require("S3_ACCESS_KEY_ID"),
        secret_access_key=_require("S3_SECRET_ACCESS_KEY"),
        max_upload_bytes=int(max_mb) * 1024 * 1024,
    )


def _normalize_db_url(url: str) -> str:
    """Accept the string exactly as Neon/Render show it; the app always uses psycopg 3."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    raise ConfigError("DATABASE_URL must be a postgresql:// connection string")


def load_settings() -> Settings:
    database_url = _normalize_db_url(_require("DATABASE_URL"))
    jwt_secret = _require("JWT_SECRET")
    if len(jwt_secret.encode()) < MIN_JWT_SECRET_BYTES:
        raise ConfigError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes")
    origins = tuple(o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip())
    if "*" in origins:
        raise ConfigError("CORS_ORIGINS must be an explicit allowlist, never '*'")
    app_base_url = os.environ.get("APP_BASE_URL", "http://localhost:3000").strip().rstrip("/")
    return Settings(
        database_url=database_url,
        jwt_secret=jwt_secret,
        cors_origins=origins,
        app_base_url=app_base_url,
        smtp=_load_smtp(),
        s3=_load_s3(),
    )


settings = load_settings()
