"""Service configuration — every value comes from the environment; missing means loud failure."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", extra="ignore")

	database_url: str  # postgresql+psycopg://user:pass@host/db
	jwt_secret: str = ""  # required before login issues tokens (checked loudly in auth)
	cors_origins: str = ""  # comma-separated allowlist, never "*"
	api_prefix: str = "/api/v1"


settings = Settings()