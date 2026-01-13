"""Application settings using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings.

    Settings can be configured via environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Server
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=12050, description="API server port")

    # Model Configuration
    planner_model: Literal["opus", "sonnet", "haiku"] = Field(
        default="opus", description="Model for planner agent"
    )
    researcher_model: Literal["opus", "sonnet", "haiku"] = Field(
        default="sonnet", description="Model for researcher agents"
    )
    synthesizer_model: Literal["opus", "sonnet", "haiku"] = Field(
        default="opus", description="Model for synthesizer agent"
    )

    # Research Settings
    max_parallel_agents: int = Field(
        default=10, ge=1, le=50, description="Maximum number of parallel researcher agents"
    )
    agent_timeout_seconds: int = Field(
        default=0, ge=0, description="Timeout for each agent in seconds. 0 means no timeout."
    )
    checkpoint_interval_seconds: int = Field(
        default=60, ge=10, le=300, description="Interval for saving checkpoints"
    )

    # Data Storage
    data_dir: Path = Field(default=Path("./data"), description="Data directory path")
    database_path: Path = Field(
        default=Path("./data/sessions.db"), description="SQLite database path"
    )
    checkpoints_dir: Path = Field(
        default=Path("./data/checkpoints"), description="Checkpoints directory path"
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        # Ensure database parent directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Creates a new instance on first call, then returns the cached instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance.

    Useful for testing or when settings need to be reloaded.
    """
    global _settings
    _settings = None
