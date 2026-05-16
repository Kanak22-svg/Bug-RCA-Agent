"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./bugcopilot.db"

    issue_provider: str = "mock"
    docs_provider: str = "mock"
    code_provider: str = "mock"

    atlassian_mcp_url: str = ""
    atlassian_mcp_token: str = ""

    github_mcp_url: str = ""
    github_mcp_token: str = ""
    github_mcp_stdio: bool = False
    github_mcp_command: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
