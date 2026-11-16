from pathlib import Path
from typing import Optional
try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:
    pass

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Minimal fallback dataclass when pydantic is not installed
    def Field(default=None, default_factory=None, description="", **kwargs):
        if default_factory is not None:
            return default_factory()
        return default
    class BaseSettings:
        pass
    class SettingsConfigDict:
        def __init__(self, **kwargs): pass



def legacy_aware(path: Path, legacy: Path) -> Path:
    """Keep using pre-rename (Kora) data at `legacy` until data exists at the new `path`."""
    return legacy if legacy.exists() and not path.exists() else path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore"
    )

    # Service Configuration
    env: str = Field(default="development", description="Environment: development, staging, production")
    port: int = Field(default=8000, description="Service HTTP port")
    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")
    allowed_origins: str = Field(
        default="",
        description="Comma-separated browser origins, besides the Studio itself, allowed to call the API",
    )
    auth_required: bool = Field(
        default=True,
        description="Require an API token on every /v1 route (set false only for throwaway local hacking)",
    )
    require_signed_manifests: bool = Field(
        default=False,
        description="Reject agent runs whose manifest is not signed with this workspace's key",
    )
    keelway_api_token: Optional[str] = Field(
        default=None,
        description="Fixed owner token for this server process; a random one is generated per launch if unset",
    )

    # Database
    database_url: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{legacy_aware(Path.home() / '.keelway' / 'keelway.db', Path.home() / '.kora' / 'kora.db')}",
        description="Async database connection string (SQLite for local dev, PostgreSQL for prod)"
    )

    # Provider Keys
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API Key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API Key")

    # Local / Edge Provider
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama or local model API base URL")
    default_local_model: str = Field(default="qwen3.5:latest", description="Preferred local model tag; falls back to an installed one")
    local_api: str = Field(default="auto", description="Local server API: auto | ollama | openai (vLLM, llama.cpp, LM Studio)")

    # Policy Defaults
    max_latency_ms: int = Field(default=15000, description="Maximum acceptable latency before fallback")
    max_cost_per_task_usd: float = Field(default=0.50, description="Cost guardrail per single task execution")
    default_timeout_seconds: float = Field(default=30.0, description="Default timeout for upstream model requests")


settings = Settings()
