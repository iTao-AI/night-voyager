from enum import StrEnum
from typing import Self

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
        return self
