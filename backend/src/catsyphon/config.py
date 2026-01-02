"""
CatSyphon Configuration.

Centralized configuration management using Pydantic Settings.
Loads configuration from environment variables.
"""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_xdg_cache_dir() -> str:
    """
    Get XDG-compliant cache directory for CatSyphon.

    Follows XDG Base Directory Specification:
    - Uses $XDG_CACHE_HOME/catsyphon if XDG_CACHE_HOME is set
    - Falls back to $HOME/.cache/catsyphon if not set
    - Returns relative path .catsyphon_cache if HOME not available (dev/testing)

    Returns:
        str: Path to cache directory
    """
    xdg_cache_home = os.getenv("XDG_CACHE_HOME")
    if xdg_cache_home:
        return str(Path(xdg_cache_home) / "catsyphon")

    home = os.getenv("HOME")
    if home:
        return str(Path(home) / ".cache" / "catsyphon")

    # Fallback for development/testing environments without HOME
    return ".catsyphon_cache"


def get_xdg_state_dir() -> str:
    """
    Get XDG-compliant state directory for CatSyphon logs.

    Follows XDG Base Directory Specification:
    - Uses $XDG_STATE_HOME/catsyphon if XDG_STATE_HOME is set
    - Falls back to $HOME/.local/state/catsyphon if not set
    - Returns relative path ./logs if HOME not available (dev/testing)

    Returns:
        str: Path to state/logs directory
    """
    xdg_state_home = os.getenv("XDG_STATE_HOME")
    if xdg_state_home:
        return str(Path(xdg_state_home) / "catsyphon" / "logs")

    home = os.getenv("HOME")
    if home:
        return str(Path(home) / ".local" / "state" / "catsyphon" / "logs")

    # Fallback for development/testing environments without HOME
    return "./logs"


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
    database_url_override: str | None = Field(
        default=None, alias="DATABASE_URL"
    )  # Optional direct override

    # Database Connection Pool (CATSYPHON_ prefixed for new settings)
    db_pool_size: int = Field(
        default=10, alias="CATSYPHON_DB_POOL_SIZE"
    )  # Base connections per worker
    db_pool_max_overflow: int = Field(
        default=10, alias="CATSYPHON_DB_POOL_MAX_OVERFLOW"
    )  # Extra connections per worker
    db_pool_timeout: int = Field(
        default=30, alias="CATSYPHON_DB_POOL_TIMEOUT"
    )  # Wait time for connection (seconds)
    db_pool_recycle: int = Field(
        default=300, alias="CATSYPHON_DB_POOL_RECYCLE"
    )  # Recycle connections after N seconds

    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        default_values = (
            "catsyphon",
            "catsyphon",
            "catsyphon_dev_password",
            "localhost",
            5432,
        )
        postgres_overridden = (
            self.postgres_db,
            self.postgres_user,
            self.postgres_password,
            self.postgres_host,
            self.postgres_port,
        ) != default_values

        if self.database_url_override and not postgres_overridden:
            return self.database_url_override

        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000

    # LLM Tagging Parameters
    llm_temperature: float = Field(
        default=0.3, alias="CATSYPHON_LLM_TEMPERATURE"
    )  # Temperature for LLM tagging (0.0 = deterministic, 1.0 = creative)

    # Tagging
    tagging_enabled: bool = False  # Enable LLM tagging by default (opt-in via flag)
    tagging_cache_dir: str = (
        f"{get_xdg_cache_dir()}/tags"  # XDG-compliant cache directory
    )
    tagging_cache_ttl_days: int = 30  # Cache time-to-live in days
    tagging_enable_cache: bool = True  # Enable caching (reduces OpenAI costs)

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # API Pagination
    api_default_page_size: int = Field(
        default=50, alias="CATSYPHON_API_DEFAULT_PAGE_SIZE"
    )  # Default items per page
    api_max_page_size: int = Field(
        default=100, alias="CATSYPHON_API_MAX_PAGE_SIZE"
    )  # Maximum items per page

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
    watch_debounce_seconds: float = 1.0  # Wait time after file event before processing
    watch_stats_interval: int = Field(
        default=30, alias="CATSYPHON_WATCH_STATS_INTERVAL"
    )  # Stats push interval in seconds

    # Daemon Manager Settings
    daemon_stats_sync_interval: int = Field(
        default=30, alias="CATSYPHON_DAEMON_STATS_SYNC_INTERVAL"
    )  # Interval for syncing stats to database
    daemon_health_check_interval: int = Field(
        default=30, alias="CATSYPHON_DAEMON_HEALTH_CHECK_INTERVAL"
    )  # Interval for health checks
    daemon_termination_timeout: int = Field(
        default=10, alias="CATSYPHON_DAEMON_TERMINATION_TIMEOUT"
    )  # Timeout for graceful daemon shutdown

    # Collector/API Ingestion Settings
    collector_batch_size: int = Field(
        default=20, alias="CATSYPHON_COLLECTOR_BATCH_SIZE"
    )  # Messages per batch for API ingestion
    collector_http_timeout: int = Field(
        default=30, alias="CATSYPHON_COLLECTOR_HTTP_TIMEOUT"
    )  # HTTP request timeout in seconds
    collector_max_retries: int = Field(
        default=3, alias="CATSYPHON_COLLECTOR_MAX_RETRIES"
    )  # Max retry attempts for failed requests

    # Application
    environment: str = "development"
    parser_modules: list[str] | str = []  # Optional additional parser module paths

    # Logging
    log_level: str = "INFO"
    log_dir: str = (
        ""  # XDG-compliant log directory (defaults to XDG state dir if empty)
    )
    log_format: str = "standard"  # standard or json
    log_console_enabled: bool = True  # Enable console (stdout/stderr) logging
    log_file_enabled: bool = True  # Enable file-based logging
    log_max_bytes: int = 10_485_760  # 10MB per log file
    log_backup_count: int = 5  # Keep 5 backup files
    log_to_stdout: bool = True  # Log INFO/DEBUG to stdout
    log_to_stderr: bool = True  # Log WARNING/ERROR/CRITICAL to stderr

    # LLM Logging
    llm_logging_enabled: bool = False  # Enable detailed LLM interaction logging
    llm_log_requests: bool = True  # Log OpenAI API requests
    llm_log_responses: bool = True  # Log OpenAI API responses
    llm_log_tokens: bool = True  # Log token usage statistics

    @property
    def log_directory(self) -> Path:
        """Get the log directory path, using XDG default if not specified."""
        if self.log_dir:
            return Path(self.log_dir).expanduser()
        return Path(get_xdg_state_dir())


# Global settings instance
settings = Settings()
