from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./bug_copilot.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM
    ANTHROPIC_API_KEY: Optional[str] = None

    # GitHub
    GITHUB_TOKEN: Optional[str] = None

    # Atlassian
    JIRA_BASE_URL: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    CONFLUENCE_BASE_URL: Optional[str] = None

    # Provider mode
    PROVIDER_MODE: str = "mock"  # mock | mcp | direct

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
