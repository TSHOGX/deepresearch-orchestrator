"""Tests for configuration management."""

import os
from pathlib import Path

import pytest

from deep_research.config import Settings, get_settings, reset_settings


class TestSettings:
    """Test Settings class."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        reset_settings()
        # Clean up any env vars we set
        env_vars = [
            "API_HOST",
            "API_PORT",
            "PLANNER_MODEL",
            "RESEARCHER_MODEL",
            "SYNTHESIZER_MODEL",
            "MAX_PARALLEL_AGENTS",
            "LOG_LEVEL",
        ]
        for var in env_vars:
            os.environ.pop(var, None)

    def test_default_values(self) -> None:
        """Test default configuration values."""
        settings = Settings()

        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 12050
        assert settings.planner_model == "opus"
        assert settings.researcher_model == "sonnet"
        assert settings.synthesizer_model == "opus"
        assert settings.max_parallel_agents == 10
        assert settings.agent_timeout_seconds == 300
        assert settings.checkpoint_interval_seconds == 60
        assert settings.log_level == "INFO"

    def test_environment_variable_override(self) -> None:
        """Test that environment variables override defaults."""
        os.environ["API_PORT"] = "8080"
        os.environ["PLANNER_MODEL"] = "sonnet"
        os.environ["MAX_PARALLEL_AGENTS"] = "5"

        settings = Settings()

        assert settings.api_port == 8080
        assert settings.planner_model == "sonnet"
        assert settings.max_parallel_agents == 5

    def test_model_validation(self) -> None:
        """Test that only valid model values are accepted."""
        os.environ["PLANNER_MODEL"] = "opus"
        settings = Settings()
        assert settings.planner_model == "opus"

        os.environ["RESEARCHER_MODEL"] = "haiku"
        settings = Settings()
        assert settings.researcher_model == "haiku"

    def test_get_settings_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reset_settings(self) -> None:
        """Test that reset_settings creates a new instance."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2

    def test_ensure_directories(self, tmp_path: Path) -> None:
        """Test that ensure_directories creates necessary directories."""
        os.environ["DATA_DIR"] = str(tmp_path / "data")
        os.environ["DATABASE_PATH"] = str(tmp_path / "data" / "sessions.db")
        os.environ["CHECKPOINTS_DIR"] = str(tmp_path / "data" / "checkpoints")

        settings = Settings()
        settings.ensure_directories()

        assert settings.data_dir.exists()
        assert settings.checkpoints_dir.exists()
        assert settings.database_path.parent.exists()

    def test_max_parallel_agents_bounds(self) -> None:
        """Test max_parallel_agents validation bounds."""
        os.environ["MAX_PARALLEL_AGENTS"] = "1"
        settings = Settings()
        assert settings.max_parallel_agents == 1

        os.environ["MAX_PARALLEL_AGENTS"] = "50"
        settings = Settings()
        assert settings.max_parallel_agents == 50

    def test_log_level_values(self) -> None:
        """Test valid log level values."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            os.environ["LOG_LEVEL"] = level
            settings = Settings()
            assert settings.log_level == level
