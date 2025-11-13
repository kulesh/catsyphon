"""
CatSyphon Configuration.

Centralized configuration management using Pydantic Settings.
Loads configuration from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    postgres_db: str = "catsyphon"
    postgres_user: str = "catsyphon"
    postgres_password: str = "catsyphon_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000

    # Tagging
    tagging_enabled: bool = False  # Enable LLM tagging by default (opt-in via flag)
    tagging_cache_dir: str = ".catsyphon_cache/tags"  # Cache directory for tags
    tagging_cache_ttl_days: int = 30  # Cache time-to-live in days
    tagging_enable_cache: bool = True  # Enable caching (reduces OpenAI costs)

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # Watch daemon
    watch_directory: str = (
        ""  # Default directory to watch (empty = require explicit path)
    )
    watch_project_name: str = ""  # Default project name for watched files
    watch_developer_username: str = ""  # Default developer username for watched files
    watch_poll_interval: int = 2  # File system polling interval in seconds
    watch_retry_interval: int = (
        300  # Retry failed files every N seconds (default: 5 minutes)
    )
    watch_max_retries: int = 3  # Maximum number of retry attempts before giving up
    watch_pid_file: str = "/tmp/catsyphon_watch.pid"  # Daemon PID file location
    watch_log_file: str = "/tmp/catsyphon_watch.log"  # Daemon log file location
    watch_debounce_seconds: float = 1.0  # Wait time after file event before processing

    # Application
    environment: str = "development"
    log_level: str = "INFO"


# Global settings instance
settings = Settings()
