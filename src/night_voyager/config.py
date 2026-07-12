from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "change-me-before-production"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NIGHT_VOYAGER_", extra="forbid")

    environment: Environment = Environment.DEVELOPMENT
    secret_key: str = DEFAULT_SECRET
    database_url: str = "postgresql+asyncpg://night_voyager_api:api-local-only@postgres:5432/night_voyager"
    demo_mode: bool = False
    demo_allow_insecure_cookie: bool = False
    allowed_origins: tuple[str, ...] = ()

    @property
    def session_cookie_secure(self) -> bool:
        return not self.demo_allow_insecure_cookie

    @property
    def authorization_mode(self) -> str:
        if self.environment is Environment.TEST:
            return "deterministic-test"
        return "server-actor-context"

    @model_validator(mode="after")
    def validate_environment_defaults(self) -> Self:
        if self.environment is Environment.TEST and self.secret_key == DEFAULT_SECRET:
            self.secret_key = "test-only-not-a-secret"
        if self.environment is Environment.PRODUCTION and self.secret_key == DEFAULT_SECRET:
            raise ValueError("production requires a non-default secret")
        if self.environment is Environment.PRODUCTION and self.demo_mode:
            raise ValueError("production disables demo mode")
        if self.environment is Environment.PRODUCTION and self.demo_allow_insecure_cookie:
            raise ValueError("production requires secure cookies")
        if self.demo_allow_insecure_cookie and not self.demo_mode:
            raise ValueError("insecure demo cookies require demo mode")
        if self.demo_allow_insecure_cookie and (
            not self.allowed_origins
            or any(not _is_loopback_http_origin(origin) for origin in self.allowed_origins)
        ):
            raise ValueError("insecure demo cookies require loopback HTTP origins")
        return self


def _is_loopback_http_origin(origin: str) -> bool:
    parsed = urlsplit(origin)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
