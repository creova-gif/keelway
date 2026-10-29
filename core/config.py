from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore"
    )

    # Service Configuration
    env: str = Field(default="development", description="Environment: development, staging, production")
    port: int = Field(default=8000, description="Service HTTP port")
    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///kora.db",
        description="Async database connection string (SQLite for local dev, PostgreSQL for prod)"
    )

    # Provider Keys
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API Key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API Key")

    # Local / Edge Provider
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama or local model API base URL")
    default_local_model: str = Field(default="qwen3.5:latest", description="Default local model tag")

    # Policy Defaults
    max_latency_ms: int = Field(default=15000, description="Maximum acceptable latency before fallback")
    max_cost_per_task_usd: float = Field(default=0.50, description="Cost guardrail per single task execution")
    default_timeout_seconds: float = Field(default=30.0, description="Default timeout for upstream model requests")


settings = Settings()
