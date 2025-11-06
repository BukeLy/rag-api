"""
Rate Limiter Module

A generic rate limiter implementation for API calls, supporting both
RPM (Requests Per Minute) and TPM (Tokens Per Minute) limits.

Created: 2025-11-06
Purpose: Prevent 429 errors from API providers (e.g., SiliconFlow)
"""

import asyncio
import time
from typing import List, Optional, Tuple
from collections import deque
from src.logger import logger


class RateLimiter:
    """
    Dual rate limiter supporting both RPM and TPM limits.

    Implements a sliding window algorithm to track requests
    and token usage within a 60-second window.
    """

    def __init__(
        self,
        requests_per_minute: int = 1000,
        tokens_per_minute: int = 50000,
        service_name: str = "API"
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            tokens_per_minute: Maximum tokens allowed per minute
            service_name: Name of the service (for logging)
        """
        self.rpm_limit = requests_per_minute
        self.tpm_limit = tokens_per_minute
        self.service_name = service_name

        # Use deque for efficient time-based cleanup
        self.request_times: deque = deque()
        self.token_usage: deque[Tuple[float, int]] = deque()

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 0) -> None:
        """
        Acquire permission to make an API call.

        Blocks if rate limits would be exceeded, waiting until
        the request can be made safely.

        Args:
            estimated_tokens: Estimated tokens for this request
        """
        async with self._lock:
            now = time.time()

            # Clean up records older than 60 seconds
            self._cleanup_old_records(now)

            # Check and wait for RPM limit
            await self._check_rpm_limit(now)

            # Check and wait for TPM limit
            if estimated_tokens > 0:
                await self._check_tpm_limit(now, estimated_tokens)

            # Record this request
            self.request_times.append(now)
            if estimated_tokens > 0:
                self.token_usage.append((now, estimated_tokens))

            # Log rate limit status (debug level)
            current_rpm = len(self.request_times)
            current_tpm = sum(tokens for _, tokens in self.token_usage)
            logger.debug(
                f"[{self.service_name}] Rate limit status: "
                f"RPM={current_rpm}/{self.rpm_limit}, "
                f"TPM={current_tpm}/{self.tpm_limit}"
            )

    def _cleanup_old_records(self, now: float) -> None:
        """Remove records older than 60 seconds."""
        cutoff_time = now - 60

        # Clean up request times
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()

        # Clean up token usage
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()

    async def _check_rpm_limit(self, now: float) -> None:
        """Check and wait if RPM limit would be exceeded."""
        if len(self.request_times) >= self.rpm_limit:
            # Calculate wait time until oldest request expires
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                logger.info(
                    f"[{self.service_name}] RPM limit reached "
                    f"({self.rpm_limit}/min), waiting {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
                # Recursive call to re-check after waiting
                now = time.time()
                self._cleanup_old_records(now)
                await self._check_rpm_limit(now)

    async def _check_tpm_limit(self, now: float, estimated_tokens: int) -> None:
        """Check and wait if TPM limit would be exceeded."""
        current_tpm = sum(tokens for _, tokens in self.token_usage)

        if current_tpm + estimated_tokens > self.tpm_limit:
            # Calculate wait time until enough tokens expire
            if self.token_usage:
                wait_time = 60 - (now - self.token_usage[0][0])
                if wait_time > 0:
                    logger.info(
                        f"[{self.service_name}] TPM limit reached "
                        f"({current_tpm}/{self.tpm_limit}), "
                        f"waiting {wait_time:.1f}s for {estimated_tokens} tokens"
                    )
                    await asyncio.sleep(wait_time)
                    # Recursive call to re-check after waiting
                    now = time.time()
                    self._cleanup_old_records(now)
                    await self._check_tpm_limit(now, estimated_tokens)

    def get_status(self) -> dict:
        """
        Get current rate limit status.

        Returns:
            Dictionary with current RPM and TPM usage
        """
        now = time.time()
        self._cleanup_old_records(now)

        current_rpm = len(self.request_times)
        current_tpm = sum(tokens for _, tokens in self.token_usage)

        return {
            "service": self.service_name,
            "rpm": {
                "current": current_rpm,
                "limit": self.rpm_limit,
                "available": max(0, self.rpm_limit - current_rpm)
            },
            "tpm": {
                "current": current_tpm,
                "limit": self.tpm_limit,
                "available": max(0, self.tpm_limit - current_tpm)
            }
        }


class AsyncSemaphoreWithRateLimit:
    """
    Combines asyncio.Semaphore with RateLimiter for comprehensive control.

    This ensures both concurrent request limits and rate limits are respected.
    """

    def __init__(
        self,
        max_concurrent: int = 16,
        requests_per_minute: int = 1000,
        tokens_per_minute: int = 50000,
        service_name: str = "API"
    ):
        """
        Initialize combined limiter.

        Args:
            max_concurrent: Maximum concurrent requests
            requests_per_minute: Maximum requests per minute
            tokens_per_minute: Maximum tokens per minute
            service_name: Name of the service
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            tokens_per_minute=tokens_per_minute,
            service_name=service_name
        )
        self.service_name = service_name

    async def __aenter__(self):
        """Acquire both semaphore and rate limit permission."""
        await self.semaphore.__aenter__()
        # For context manager, we don't estimate tokens
        await self.rate_limiter.acquire(0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore."""
        await self.semaphore.__aexit__(exc_type, exc_val, exc_tb)

    async def acquire_with_tokens(self, estimated_tokens: int = 0):
        """
        Acquire permission with token estimation.

        Args:
            estimated_tokens: Estimated tokens for this request

        Returns:
            Context manager for the acquired permission
        """
        await self.semaphore.acquire()
        try:
            await self.rate_limiter.acquire(estimated_tokens)
            return self
        except Exception as e:
            # Release semaphore if rate limit acquisition fails
            self.semaphore.release()
            raise

    def release(self):
        """Release the semaphore."""
        self.semaphore.release()

    def get_status(self) -> dict:
        """Get current status including semaphore and rate limits."""
        status = self.rate_limiter.get_status()
        status["concurrent"] = {
            "available": self.semaphore._value,
            "limit": self.semaphore._initial_value
        }
        return status


# Global rate limiters for different services (singleton pattern)
_limiters = {}


def get_rate_limiter(
    service: str,
    max_concurrent: Optional[int] = None,
    requests_per_minute: Optional[int] = None,
    tokens_per_minute: Optional[int] = None
) -> AsyncSemaphoreWithRateLimit:
    """
    Get or create a rate limiter for a specific service.

    Uses singleton pattern to ensure one limiter per service.

    Args:
        service: Service name (e.g., "llm", "embedding", "rerank")
        max_concurrent: Override max concurrent requests
        requests_per_minute: Override RPM limit
        tokens_per_minute: Override TPM limit

    Returns:
        AsyncSemaphoreWithRateLimit instance
    """
    if service not in _limiters:
        # Default values based on service type
        defaults = {
            "llm": (8, 800, 40000),
            "embedding": (32, 1600, 400000),
            "rerank": (16, 1600, 400000),
            "ds_ocr": (8, 800, 40000)
        }

        default_concurrent, default_rpm, default_tpm = defaults.get(
            service, (16, 1000, 50000)
        )

        _limiters[service] = AsyncSemaphoreWithRateLimit(
            max_concurrent=max_concurrent or default_concurrent,
            requests_per_minute=requests_per_minute or default_rpm,
            tokens_per_minute=tokens_per_minute or default_tpm,
            service_name=service.upper()
        )

        logger.info(
            f"Created rate limiter for {service.upper()}: "
            f"concurrent={max_concurrent or default_concurrent}, "
            f"RPM={requests_per_minute or default_rpm}, "
            f"TPM={tokens_per_minute or default_tpm}"
        )

    return _limiters[service]