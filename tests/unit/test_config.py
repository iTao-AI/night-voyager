import pytest
from pydantic import ValidationError

from night_voyager.config import Environment, Settings


def test_test_environment_has_deterministic_defaults() -> None:
    settings = Settings.model_validate({"environment": "test"})

    assert settings.environment is Environment.TEST
    assert settings.authorization_mode == "deterministic-test"
    assert settings.secret_key == "test-only-not-a-secret"


def test_production_rejects_the_default_secret() -> None:
    with pytest.raises(ValidationError, match="production requires a non-default secret"):
        Settings.model_validate({"environment": "production"})


def test_unknown_environment_is_rejected_instead_of_changing_authorization() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": "staging-typo"})
