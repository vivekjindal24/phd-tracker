"""Environment configuration, validated loudly at import time (fail fast at startup)."""

import os
import re
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
AI_VARS = ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL")


@dataclass(frozen=True)
class Ai:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class S3:
    endpoint: str
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    max_upload_bytes: int


GOOGLE_VARS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
MICROSOFT_VARS = ("MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET", "MICROSOFT_TENANT_ID")
_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


@dataclass(frozen=True)
class OidcProvider:
    name: str
    client_id: str
    client_secret: str
    issuer: str
    tenant_id: str | None = None  # Microsoft only: tokens from other tenants are refused

    @property
    def discovery_url(self) -> str:
        return f"{self.issuer}/.well-known/openid-configuration"


@dataclass(frozen=True)
class Sso:
    providers: dict[str, OidcProvider]
    allowed_domains: tuple[str, ...]
    api_public_url: str


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    cors_origins: tuple[str, ...]
    app_base_url: str
    smtp: Smtp | None
    s3: S3
    ai: Ai | None
    sso: Sso | None = None
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


def _load_ai() -> Ai | None:
    """All-or-nothing, like SMTP: none set = supervisors write seminar points by hand."""
    values = {name: os.environ.get(name, "").strip() for name in AI_VARS}
    if not any(values.values()):
        return None
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError("AI is partly configured; also set " + ", ".join(missing))
    if not values["AI_BASE_URL"].startswith(("https://", "http://")):
        raise ConfigError("AI_BASE_URL must be an http(s) URL")
    return Ai(
        base_url=values["AI_BASE_URL"].rstrip("/"),
        api_key=values["AI_API_KEY"],
        model=values["AI_MODEL"],
    )


def _all_or_none(names: tuple[str, ...], what: str) -> dict[str, str] | None:
    values = {name: os.environ.get(name, "").strip() for name in names}
    if not any(values.values()):
        return None
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError(f"{what} is partly configured; also set " + ", ".join(missing))
    return values


def _load_sso() -> Sso | None:
    """University-email login (SECURITY.md §1). Each provider all-or-nothing; any provider
    needs the allowed email domains and the API's public URL (the OIDC redirect target)."""
    providers: dict[str, OidcProvider] = {}
    google = _all_or_none(GOOGLE_VARS, "Google sign-in")
    if google:
        providers["google"] = OidcProvider(
            "google",
            google["GOOGLE_CLIENT_ID"],
            google["GOOGLE_CLIENT_SECRET"],
            "https://accounts.google.com",
        )
    microsoft = _all_or_none(MICROSOFT_VARS, "Microsoft sign-in")
    if microsoft:
        tenant = microsoft["MICROSOFT_TENANT_ID"].lower()
        if not _GUID.match(tenant):
            raise ConfigError("MICROSOFT_TENANT_ID must be the university's tenant GUID")
        providers["microsoft"] = OidcProvider(
            "microsoft",
            microsoft["MICROSOFT_CLIENT_ID"],
            microsoft["MICROSOFT_CLIENT_SECRET"],
            f"https://login.microsoftonline.com/{tenant}/v2.0",
            tenant,
        )
    if not providers:
        return None
    domains = tuple(
        d.strip().lower().lstrip("@")
        for d in os.environ.get("SSO_ALLOWED_DOMAINS", "").split(",")
        if d.strip()
    )
    if not domains:
        raise ConfigError("single sign-on needs SSO_ALLOWED_DOMAINS (e.g. univ.ac.in)")
    bad = [d for d in domains if not _DOMAIN.match(d)]
    if bad:
        raise ConfigError(f"SSO_ALLOWED_DOMAINS has invalid entries: {', '.join(bad)}")
    api_url = _require("API_PUBLIC_URL").rstrip("/")
    if not api_url.startswith(("https://", "http://")):
        raise ConfigError("API_PUBLIC_URL must be an http(s) URL")
    return Sso(providers=providers, allowed_domains=domains, api_public_url=api_url)


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


_ORIGIN = re.compile(r"^https?://[a-z0-9.-]+(:\d{1,5})?$")


def _parse_origins(raw: str) -> tuple[str, ...]:
    """A browser Origin is exactly scheme://host[:port] — no path, no trailing slash. Tidy
    harmless paste noise (quotes, spaces, trailing '/'); fail loudly on anything else."""
    origins = []
    for item in raw.split(","):
        origin = item.strip().strip("'\"").strip().rstrip("/").lower()
        if not origin:
            continue
        if origin == "*":
            raise ConfigError("CORS_ORIGINS must be an explicit allowlist, never '*'")
        if not _ORIGIN.match(origin):
            raise ConfigError(f"CORS_ORIGINS entry {item.strip()!r} is not like https://host")
        origins.append(origin)
    return tuple(origins)


def load_settings() -> Settings:
    database_url = _normalize_db_url(_require("DATABASE_URL"))
    jwt_secret = _require("JWT_SECRET")
    if len(jwt_secret.encode()) < MIN_JWT_SECRET_BYTES:
        raise ConfigError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes")
    origins = _parse_origins(os.environ.get("CORS_ORIGINS", ""))
    app_base_url = os.environ.get("APP_BASE_URL", "http://localhost:3000").strip().rstrip("/")
    return Settings(
        database_url=database_url,
        jwt_secret=jwt_secret,
        cors_origins=origins,
        app_base_url=app_base_url,
        smtp=_load_smtp(),
        s3=_load_s3(),
        ai=_load_ai(),
        sso=_load_sso(),
    )


settings = load_settings()
