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
        while True:
            # Calculate wait time under lock
            wait_time = 0
            wait_reason = None
            async with self._lock:
                now = time.time()

                # Clean up records older than 60 seconds
                self._cleanup_old_records(now)

                # Check RPM limit
                rpm_wait = self._get_rpm_wait_time(now)

                # Check TPM limit
                tpm_wait = 0
                if estimated_tokens > 0:
                    tpm_wait = self._get_tpm_wait_time(now, estimated_tokens)

                # Use the longer wait time
                wait_time = max(rpm_wait, tpm_wait)

                # Determine wait reason for logging
                if wait_time > 0:
                    if rpm_wait >= tpm_wait:
                        wait_reason = "rpm"
                    else:
                        wait_reason = "tpm"

                # If no wait needed, record request and return
                if wait_time <= 0:
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
                    return

            # Wait without holding lock
            if wait_time > 0:
                # Log based on wait reason
                if wait_reason == "rpm":
                    logger.info(
                        f"[{self.service_name}] RPM limit reached "
                        f"({self.rpm_limit}/min), waiting {wait_time:.1f}s"
                    )
                else:
                    logger.info(
                        f"[{self.service_name}] TPM limit reached, "
                        f"waiting {wait_time:.1f}s for {estimated_tokens} tokens"
                    )
                await asyncio.sleep(wait_time)

    def _cleanup_old_records(self, now: float) -> None:
        """Remove records older than 60 seconds."""
        cutoff_time = now - 60

        # Clean up request times
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()

        # Clean up token usage
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()

    def _get_rpm_wait_time(self, now: float) -> float:
        """Calculate wait time needed for RPM limit."""
        if len(self.request_times) >= self.rpm_limit:
            # Calculate wait time until oldest request expires
            wait_time = 60 - (now - self.request_times[0])
            return max(0, wait_time)
        return 0

    def _get_tpm_wait_time(self, now: float, estimated_tokens: int) -> float:
        """Calculate wait time needed for TPM limit."""
        current_tpm = sum(tokens for _, tokens in self.token_usage)

        if current_tpm + estimated_tokens > self.tpm_limit:
            # Need to wait for some tokens to expire
            if self.token_usage:
                # Simple strategy: wait for the oldest token record to expire
                # More sophisticated: calculate exactly when enough tokens will expire
                wait_time = 60 - (now - self.token_usage[0][0])
                return max(0, wait_time)
        return 0

    async def get_status(self) -> dict:
        """
        Get current rate limit status.

        Returns:
            Dictionary with current RPM and TPM usage
        """
        async with self._lock:
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
        self.max_concurrent = max_concurrent  # Store for external access
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

    async def get_status(self) -> dict:
        """Get current status including semaphore and rate limits."""
        status = await self.rate_limiter.get_status()
        status["concurrent"] = {
            "available": self.semaphore._value,
            "limit": self.semaphore._initial_value
        }
        return status


# Global rate limiters for different services (singleton pattern)
_limiters = {}


def calculate_optimal_concurrent(
    requests_per_minute: int,
    tokens_per_minute: int,
    avg_tokens_per_request: int = 3500,
    avg_request_duration_seconds: float = 2.0
) -> int:
    """
    Calculate optimal concurrent requests based on request duration and TPM/RPM limits.

    **Critical Fix**: The old formula assumed all concurrent requests could fire simultaneously,
    causing instant TPM exhaustion. The new formula uses actual request duration.

    **Problem**: If concurrent=800 and all fire at once:
        800 workers × 500 tokens = 400,000 tokens (instant TPM limit!)

    **Solution**: Calculate concurrent based on how many tokens can be consumed during request duration:
        concurrent = (TPM × duration / 60) / avg_tokens

    **Physical Meaning**:
        - If a request takes T seconds, during that time you can use (TPM × T/60) tokens
        - Divide by avg_tokens to get how many concurrent requests can run

    Args:
        requests_per_minute: Maximum requests per minute
        tokens_per_minute: Maximum tokens per minute
        avg_tokens_per_request: Average tokens per request (default: 3500)
        avg_request_duration_seconds: Average API response time in seconds (default: 2.0)
            - Embedding: ~1-2 seconds (lightweight)
            - LLM: ~3-5 seconds (text generation)
            - Rerank: ~1-2 seconds (lightweight)

    Returns:
        int: Safe concurrent count (≥2)

    Examples:
        >>> # Embedding: TPM=400000, duration=1s, avg_tokens=500
        >>> calculate_optimal_concurrent(1600, 400000, 500, 1.0)
        13  # (400000 × 1/60) / 500 = 13.33 → min(1600, 13) = 13

        >>> # LLM: TPM=40000, duration=3s, avg_tokens=3500
        >>> calculate_optimal_concurrent(800, 40000, 3500, 3.0)
        2  # (40000 × 3/60) / 3500 = 0.57 → max(2, 0) = 2
    """
    # RPM-based limit (simple: how many requests per minute)
    concurrent_by_rpm = requests_per_minute

    # TPM-based limit (physics-based calculation)
    # During request_duration seconds, we can consume: TPM × (duration / 60) tokens
    # Divide by avg_tokens to get concurrent count
    tokens_per_duration = tokens_per_minute * (avg_request_duration_seconds / 60.0)
    concurrent_by_tpm = int(tokens_per_duration / avg_tokens_per_request)

    # Take the minimum to ensure we don't exceed either limit
    optimal = min(concurrent_by_rpm, concurrent_by_tpm)

    # Ensure at least 2 concurrent (minimum for reasonable performance)
    return max(2, optimal)


def get_rate_limiter(
    service: str,
    max_concurrent: Optional[int] = None,
    requests_per_minute: Optional[int] = None,
    tokens_per_minute: Optional[int] = None
) -> AsyncSemaphoreWithRateLimit:
    """
    Get or create a rate limiter for a specific service.

    Uses singleton pattern to ensure one limiter per service.

    Configuration Priority (New Design):
    1. Explicit max_concurrent parameter (tenant RateLimiter config)
    2. Environment variable {SERVICE}_MAX_ASYNC (expert mode)
    3. Auto-calculate based on TPM/RPM (default behavior)

    Auto-calculation Formula:
        concurrent = min(RPM, TPM / avg_tokens_per_request)

    Average Token Estimation:
        - LLM: 3500 tokens/request (insert + query scenarios)
        - Embedding: 500 tokens/request (batch encoding)
        - Rerank: 500 tokens/request (document scoring)

    Args:
        service: Service name (e.g., "llm", "embedding", "rerank")
        max_concurrent: Override max concurrent (tenant RateLimiter config)
        requests_per_minute: Override RPM limit (tenant config)
        tokens_per_minute: Override TPM limit (tenant config)

    Returns:
        AsyncSemaphoreWithRateLimit instance

    Raises:
        ValueError: If calculated concurrent < 1 and cannot proceed
    """
    if service not in _limiters:
        # Import config for global defaults
        from src.config import config

        # Token estimation per service (based on research)
        avg_tokens_map = {
            "llm": 3500,       # Insert: 2840, Query: 3000-5000, Conservative: 3500
            "embedding": 500,  # Batch encoding average
            "rerank": 500,     # Document scoring average
            "ds_ocr": 3500     # Similar to LLM (OCR + description)
        }

        # Request duration estimation per service (seconds)
        request_duration_map = {
            "llm": 3.0,        # Text generation: ~3-5 seconds
            "embedding": 1.0,  # Batch encoding: ~1-2 seconds
            "rerank": 1.0,     # Document scoring: ~1-2 seconds
            "ds_ocr": 3.0      # OCR + generation: ~3-5 seconds
        }

        # Default RPM/TPM values (used if not provided)
        default_rpm_tpm = {
            "llm": (800, 40000),
            "embedding": (1600, 400000),
            "rerank": (1600, 400000),
            "ds_ocr": (800, 40000)
        }

        default_rpm, default_tpm = default_rpm_tpm.get(service, (1000, 50000))
        avg_tokens = avg_tokens_map.get(service, 3500)
        request_duration = request_duration_map.get(service, 2.0)

        # Get effective RPM/TPM (tenant config > global config)
        effective_rpm = requests_per_minute or default_rpm
        effective_tpm = tokens_per_minute or default_tpm

        # Determine final concurrent value
        final_concurrent = None
        config_source = None

        # Priority 1: Explicit max_concurrent parameter (tenant RateLimiter config)
        if max_concurrent is not None:
            final_concurrent = max_concurrent
            config_source = "tenant"

        # Priority 2: Environment variable (expert mode)
        if final_concurrent is None:
            if service == "llm":
                env_max_async = getattr(config.llm, 'max_async', None)
            elif service == "embedding":
                env_max_async = getattr(config.embedding, 'max_async', None)
            elif service == "rerank":
                env_max_async = getattr(config.rerank, 'max_async', None)
            elif service == "ds_ocr":
                env_max_async = getattr(config.ds_ocr, 'max_async', None) if hasattr(config, 'ds_ocr') else None
            else:
                env_max_async = None

            if env_max_async is not None:
                final_concurrent = env_max_async
                config_source = "env"

        # Priority 3: Auto-calculate (default behavior)
        if final_concurrent is None:
            final_concurrent = calculate_optimal_concurrent(
                requests_per_minute=effective_rpm,
                tokens_per_minute=effective_tpm,
                avg_tokens_per_request=avg_tokens,
                avg_request_duration_seconds=request_duration
            )
            config_source = "auto"

        # Edge case: If calculated < 2, log warning and set to 2
        if final_concurrent < 2:
            logger.warning(
                f"[{service.upper()}] Calculated concurrent < 2 "
                f"(RPM={effective_rpm}, TPM={effective_tpm}, avg_tokens={avg_tokens}, duration={request_duration}s). "
                f"Setting to 2. Consider increasing TPM/RPM limits."
            )
            final_concurrent = 2

        # Create rate limiter instance
        _limiters[service] = AsyncSemaphoreWithRateLimit(
            max_concurrent=final_concurrent,
            requests_per_minute=effective_rpm,
            tokens_per_minute=effective_tpm,
            service_name=service.upper()
        )

        # Log configuration details
        if config_source == "auto":
            logger.info(
                f"Created rate limiter for {service.upper()}: "
                f"concurrent={final_concurrent} (auto: TPM={effective_tpm}, RPM={effective_rpm}, "
                f"avg_tokens={avg_tokens}, duration={request_duration}s), "
                f"RPM={effective_rpm}, TPM={effective_tpm}"
            )
        else:
            logger.info(
                f"Created rate limiter for {service.upper()}: "
                f"concurrent={final_concurrent} ({config_source}), "
                f"RPM={effective_rpm}, TPM={effective_tpm}"
            )

    return _limiters[service]