from typing import List, Optional, Dict, Any
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise Agentic Governance OS"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    DATABASE_URL: str
    REDIS_URL: str

    GROQ_API_KEY: str
    DEFAULT_LLM_MODEL: str = "llama-3.1-70b-versatile"

    CORE_BANKING_API_URL: str = "https://sandbox.enterprise-bank.local/api"
    CORE_BANKING_CLIENT_ID: str = "placeholder_id"
    CORE_BANKING_CLIENT_SECRET: str = "placeholder_secret"

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    REQUIRE_MFA: bool = False
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
