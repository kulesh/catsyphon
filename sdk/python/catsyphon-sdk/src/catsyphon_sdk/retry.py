"""
Retry logic with exponential backoff.

Provides decorators and utilities for retrying failed operations.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 0.5
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_status_codes: set[int] = field(
        default_factory=lambda: {408, 429, 500, 502, 503, 504}
    )


class RetryableError(Exception):
    """Error that should trigger a retry."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class NonRetryableError(Exception):
    """Error that should not be retried."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """
    Calculate delay before next retry using exponential backoff.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    import random

    delay = config.initial_delay * (config.exponential_base**attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add up to 25% jitter to prevent thundering herd
        jitter = delay * 0.25 * random.random()
        delay += jitter

    return delay


def with_retry(config: Optional[RetryConfig] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for adding retry logic to synchronous functions.

    Args:
        config: Retry configuration (uses defaults if not provided)

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RetryableError as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_retries} for {func.__name__}: "
                            f"{e}, waiting {delay:.2f}s"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}: {e}"
                        )
                except NonRetryableError:
                    raise
                except httpx.RequestError as e:
                    last_exception = RetryableError(f"Network error: {e}")
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_retries} for {func.__name__}: "
                            f"network error, waiting {delay:.2f}s"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}"
                        )

            raise last_exception or RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


def with_async_retry(config: Optional[RetryConfig] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration (uses defaults if not provided)

    Returns:
        Decorated async function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except RetryableError as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_retries} for {func.__name__}: "
                            f"{e}, waiting {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}: {e}"
                        )
                except NonRetryableError:
                    raise
                except httpx.RequestError as e:
                    last_exception = RetryableError(f"Network error: {e}")
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_retries} for {func.__name__}: "
                            f"network error, waiting {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}"
                        )

            raise last_exception or RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


def check_response(response: httpx.Response, config: RetryConfig) -> None:
    """
    Check HTTP response and raise appropriate error.

    Args:
        response: HTTP response to check
        config: Retry configuration

    Raises:
        RetryableError: If the error should be retried
        NonRetryableError: If the error should not be retried
    """
    if response.is_success:
        return

    status_code = response.status_code

    if status_code in config.retryable_status_codes:
        raise RetryableError(
            f"HTTP {status_code}: {response.text[:200]}",
            status_code=status_code,
        )
    else:
        raise NonRetryableError(
            f"HTTP {status_code}: {response.text[:200]}",
            status_code=status_code,
        )
