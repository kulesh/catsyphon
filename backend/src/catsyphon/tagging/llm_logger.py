"""
LLM interaction logging for OpenAI API calls.

Provides detailed logging of LLM requests and responses for debugging,
cost tracking, and auditing purposes.
"""

import json
import logging
import logging.handlers
import time
from datetime import datetime, timezone
from typing import Any, Optional

from catsyphon.config import settings
from catsyphon.models.parsed import ParsedConversation

logger = logging.getLogger(__name__)


class LLMLogger:
    """
    Logger for LLM (OpenAI) API interactions.

    Logs requests, responses, token usage, and errors to a separate log file
    when LLM logging is enabled in configuration.
    """

    def __init__(self):
        """Initialize LLM logger with separate file handler."""
        self.llm_logger = logging.getLogger("catsyphon.llm")
        self.enabled = settings.llm_logging_enabled

        if self.enabled and settings.log_file_enabled:
            self._setup_file_handler()

    def _setup_file_handler(self) -> None:
        """Setup dedicated file handler for LLM logs."""
        log_dir = settings.log_directory
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create llm subdirectory
        llm_dir = log_dir / "llm"
        llm_dir.mkdir(parents=True, exist_ok=True)

        # LLM requests log
        llm_log_path = llm_dir / "requests.log"

        handler = logging.handlers.RotatingFileHandler(
            llm_log_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )

        # Use structured format for easier parsing
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        self.llm_logger.addHandler(handler)
        self.llm_logger.setLevel(logging.INFO)
        self.llm_logger.propagate = False  # Don't propagate to root logger

    def log_request(
        self,
        conversation: ParsedConversation,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Log OpenAI API request details.

        Args:
            conversation: Parsed conversation being tagged
            model: OpenAI model name
            prompt: Full prompt sent to API
            max_tokens: Maximum tokens requested
            temperature: Temperature parameter

        Returns:
            str: Request ID for correlating with response
        """
        if not self.enabled or not settings.llm_log_requests:
            return ""

        request_id = f"{conversation.session_id}_{int(time.time() * 1000)}"

        # Sanitize prompt for logging (limit length)
        prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt

        log_entry = {
            "type": "request",
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "session_id": conversation.session_id,
            "message_count": len(conversation.messages),
            "parameters": {
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            "prompt_preview": prompt_preview,
            "prompt_length": len(prompt),
        }

        self.llm_logger.info(f"REQUEST: {json.dumps(log_entry)}")
        return request_id

    def log_response(
        self,
        request_id: str,
        response: Any,
        duration_ms: float,
    ) -> None:
        """
        Log OpenAI API response details.

        Args:
            request_id: Request ID from log_request()
            response: OpenAI API response object
            duration_ms: Request duration in milliseconds
        """
        if not self.enabled or not settings.llm_log_responses:
            return

        try:
            # Extract response details
            content = response.choices[0].message.content if response.choices else ""
            finish_reason = (
                response.choices[0].finish_reason if response.choices else "unknown"
            )

            log_entry = {
                "type": "response",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": response.model,
                "finish_reason": finish_reason,
                "content_length": len(content),
                "duration_ms": round(duration_ms, 2),
            }

            # Add token usage if available and enabled
            if (
                settings.llm_log_tokens
                and hasattr(response, "usage")
                and response.usage
            ):
                log_entry["tokens"] = {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens,
                }

            # Include sanitized content preview
            if content:
                content_preview = (
                    content[:200] + "..." if len(content) > 200 else content
                )
                log_entry["content_preview"] = content_preview

            self.llm_logger.info(f"RESPONSE: {json.dumps(log_entry)}")

        except Exception as e:
            logger.error(f"Failed to log LLM response: {e}", exc_info=True)

    def log_error(
        self,
        request_id: str,
        error: Exception,
        conversation: Optional[ParsedConversation] = None,
    ) -> None:
        """
        Log OpenAI API error.

        Args:
            request_id: Request ID from log_request()
            error: Exception that occurred
            conversation: Optional conversation context
        """
        if not self.enabled:
            return

        log_entry = {
            "type": "error",
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }

        if conversation:
            log_entry["session_id"] = conversation.session_id

        self.llm_logger.error(f"ERROR: {json.dumps(log_entry)}")

    def log_cache_hit(
        self,
        conversation: ParsedConversation,
    ) -> None:
        """
        Log cache hit (no API call made).

        Args:
            conversation: Parsed conversation
        """
        if not self.enabled:
            return

        log_entry = {
            "type": "cache_hit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": conversation.session_id,
            "message_count": len(conversation.messages),
        }

        self.llm_logger.info(f"CACHE_HIT: {json.dumps(log_entry)}")


# Global LLM logger instance
llm_logger = LLMLogger()
