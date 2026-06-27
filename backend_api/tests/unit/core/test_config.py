import pytest
import os
from pydantic import ValidationError
from typing import List


def test_settings_instantiation_defaults() -> None:
    os.environ["SECRET_KEY"] = "test_secret_key_12345"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["GROQ_API_KEY"] = "test_groq_key"

    from src.core.config import Settings

    settings = Settings()

    assert settings.PROJECT_NAME == "Enterprise Agentic Governance OS"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.SECRET_KEY == "test_secret_key_12345"
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert settings.REFRESH_TOKEN_EXPIRE_MINUTES == 1440
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/db"
    assert settings.REDIS_URL == "redis://localhost:6379/0"
    assert settings.GROQ_API_KEY == "test_groq_key"
    assert settings.DEFAULT_LLM_MODEL == "llama-3.1-70b-versatile"
    assert settings.ENVIRONMENT == "development"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.REQUIRE_MFA is False
    assert settings.MAX_LOGIN_ATTEMPTS == 5
    assert settings.LOCKOUT_DURATION_MINUTES == 15
    assert isinstance(settings.BACKEND_CORS_ORIGINS, list)


def test_settings_cors_origins_string_parsing() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"
    os.environ["BACKEND_CORS_ORIGINS"] = "http://localhost:3000, https://example.com"

    from src.core.config import Settings

    settings = Settings()

    assert len(settings.BACKEND_CORS_ORIGINS) == 2
    assert str(settings.BACKEND_CORS_ORIGINS[0]) == "http://localhost:3000/"
    assert str(settings.BACKEND_CORS_ORIGINS[1]) == "https://example.com/"


def test_settings_cors_origins_json_list_parsing() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"
    os.environ["BACKEND_CORS_ORIGINS"] = (
        '["http://localhost:8080", "https://app.example.com"]'
    )

    from src.core.config import Settings

    settings = Settings()

    assert len(settings.BACKEND_CORS_ORIGINS) == 2
    assert str(settings.BACKEND_CORS_ORIGINS[0]) == "http://localhost:8080/"
    assert str(settings.BACKEND_CORS_ORIGINS[1]) == "https://app.example.com/"


def test_settings_cors_origins_empty() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"
    os.environ["BACKEND_CORS_ORIGINS"] = ""

    from src.core.config import Settings

    settings = Settings()

    assert len(settings.BACKEND_CORS_ORIGINS) == 0


def test_settings_cors_origins_invalid_url() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"
    os.environ["BACKEND_CORS_ORIGINS"] = "not_a_valid_url"

    from src.core.config import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_missing_secret_key() -> None:
    if "SECRET_KEY" in os.environ:
        del os.environ["SECRET_KEY"]
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "SECRET_KEY" in str(exc_info.value)


def test_settings_missing_database_url() -> None:
    os.environ["SECRET_KEY"] = "test"
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "DATABASE_URL" in str(exc_info.value)


def test_settings_missing_redis_url() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    if "REDIS_URL" in os.environ:
        del os.environ["REDIS_URL"]
    os.environ["GROQ_API_KEY"] = "test"

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "REDIS_URL" in str(exc_info.value)


def test_settings_missing_groq_api_key() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    if "GROQ_API_KEY" in os.environ:
        del os.environ["GROQ_API_KEY"]

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "GROQ_API_KEY" in str(exc_info.value)


def test_settings_override_custom_values() -> None:
    os.environ["SECRET_KEY"] = "test_custom"
    os.environ["DATABASE_URL"] = "test_custom"
    os.environ["REDIS_URL"] = "test_custom"
    os.environ["GROQ_API_KEY"] = "test_custom"
    os.environ["PROJECT_NAME"] = "Custom Name"
    os.environ["ENVIRONMENT"] = "staging"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["REQUIRE_MFA"] = "True"
    os.environ["MAX_LOGIN_ATTEMPTS"] = "10"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

    from src.core.config import Settings

    settings = Settings()

    assert settings.PROJECT_NAME == "Custom Name"
    assert settings.ENVIRONMENT == "staging"
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.REQUIRE_MFA is True
    assert settings.MAX_LOGIN_ATTEMPTS == 10
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60


def test_settings_invalid_type_conversion() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"
    os.environ["MAX_LOGIN_ATTEMPTS"] = "not_an_integer"

    from src.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "MAX_LOGIN_ATTEMPTS" in str(exc_info.value)


def test_settings_boolean_parsing_from_env() -> None:
    os.environ["SECRET_KEY"] = "test"
    os.environ["DATABASE_URL"] = "test"
    os.environ["REDIS_URL"] = "test"
    os.environ["GROQ_API_KEY"] = "test"

    from src.core.config import Settings

    os.environ["REQUIRE_MFA"] = "true"
    assert Settings().REQUIRE_MFA is True

    os.environ["REQUIRE_MFA"] = "1"
    assert Settings().REQUIRE_MFA is True

    os.environ["REQUIRE_MFA"] = "false"
    assert Settings().REQUIRE_MFA is False

    os.environ["REQUIRE_MFA"] = "0"
    assert Settings().REQUIRE_MFA is False
