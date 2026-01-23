"""
Retry handler with exponential backoff for API requests.
"""

import threading
import time
import random
import requests
from typing import Callable

from algebras.services.rate_limiter import RateLimiter


class RetryHandler:
    """Thread-safe retry handler with exponential backoff for 429 errors."""

    def __init__(
        self,
        rate_limiter: RateLimiter,
        max_retries: int = 5,
        initial_wait: float = 1.0,
    ):
        """
        Initialize RetryHandler.

        Args:
            rate_limiter: RateLimiter instance for coordinating rate limits
            max_retries: Maximum number of retry attempts (default: 5)
            initial_wait: Initial wait time in seconds (default: 1.0)
        """
        self._rate_limiter = rate_limiter
        self._max_retries = max_retries
        self._initial_wait = initial_wait

        # Shared state for coordinating retries across parallel batches
        self._lock = threading.Lock()
        self._backoff_until = 0.0  # Timestamp until which we should back off
        self._consecutive_429_count = 0  # Track consecutive 429 errors across all batches
        self._last_429_time = 0.0  # Timestamp of last 429 error

    def execute_with_retry(
        self, api_call_func: Callable[[], requests.Response]
    ) -> requests.Response:
        """
        Execute an API call with retry logic for 429 errors only.
        5xx errors are immediately raised without retry.

        Args:
            api_call_func: Callable that makes the API request and returns a response

        Returns:
            Response object from the API call

        Raises:
            Exception: If 5xx error occurs (no retry) or all retries are exhausted for 429 errors
        """
        wait_time = self._initial_wait

        for attempt in range(self._max_retries + 1):
            try:
                # Check shared rate limit state and wait if needed
                with self._lock:
                    current_time = time.time()
                    if self._backoff_until > current_time:
                        wait_needed = self._backoff_until - current_time
                        print(
                            f"  ⚠ Waiting for shared rate limit backoff: {wait_needed:.1f} seconds..."
                        )
                        time.sleep(wait_needed)

                # Enforce rate limit
                self._rate_limiter.wait_if_needed()

                response = api_call_func()

                # For 5xx errors, immediately raise exception without retry
                # Exception will be caught by batch handler, process will continue
                if 500 <= response.status_code < 600:
                    error_msg = f"Error from Algebras AI API: {response.status_code} - {response.text}"
                    raise Exception(error_msg)

                # Check for retryable errors (only 429, not 5xx)
                is_retryable_error = response.status_code == 429

                # If successful or non-retryable error, reset consecutive 429 counter and return immediately
                if not is_retryable_error:
                    # Reset consecutive 429 count on successful request
                    with self._lock:
                        if response.status_code == 200:
                            self._consecutive_429_count = 0
                    return response

                # Handle retryable errors (only 429, 5xx already handled above)
                if attempt < self._max_retries:
                    # For 429 errors, use current wait_time (initialized to initial_wait)
                    # It will be adjusted below based on consecutive 429 count

                    # Update shared backoff state (only for 429 errors)
                    with self._lock:
                        current_time = time.time()

                        # Track consecutive 429 errors (reset if more than 60 seconds since last 429)
                        if current_time - self._last_429_time > 60:
                            self._consecutive_429_count = 0
                        self._consecutive_429_count += 1
                        self._last_429_time = current_time

                        # Increase backoff more aggressively when we see multiple consecutive 429s
                        # Multiply wait time by a factor based on consecutive 429 count
                        # This helps when multiple batches hit 429 simultaneously
                        if self._consecutive_429_count > 1:
                            # Add extra backoff: 0.5s per consecutive 429 (capped at 5s extra)
                            extra_backoff = min(self._consecutive_429_count * 0.5, 5.0)
                            wait_time = wait_time + extra_backoff

                    # Add jitter to prevent thundering herd (0-20% of wait time)
                    jitter = random.uniform(0, wait_time * 0.2)
                    actual_wait = wait_time + jitter

                    # Set shared backoff to the maximum of current backoff or our wait time (only for 429)
                    with self._lock:
                        self._backoff_until = max(
                            self._backoff_until,
                            current_time + actual_wait,
                        )

                    # Wait for our backoff period (with jitter)
                    print(
                        f"  ⚠ Rate limited (429). Retrying in {actual_wait:.1f} seconds... (attempt {attempt + 1}/{self._max_retries})"
                    )
                    time.sleep(actual_wait)
                    wait_time *= 2  # Exponential backoff
                else:
                    # Last attempt failed with 429
                    error_msg = f"Error from Algebras AI API: 429 Too Many Requests - {response.text}"
                    raise Exception(error_msg)

            except requests.exceptions.RequestException as e:
                # Network errors or other request exceptions - re-raise immediately
                # These are not retryable errors
                raise Exception(f"Request failed: {str(e)}")
            except Exception as e:
                # For other exceptions, check if it's a retryable error with response (only 429)
                # 5xx errors are already handled above and will be re-raised
                if hasattr(e, "response") and hasattr(e.response, "status_code"):
                    status_code = e.response.status_code
                    # Only retry 429 errors, not 5xx
                    is_retryable = status_code == 429

                    if is_retryable and attempt < self._max_retries:
                        # For 429 errors, use current wait_time
                        # Update shared backoff state (only for 429 errors)
                        with self._lock:
                            current_time = time.time()

                            # Track consecutive 429 errors (reset if more than 60 seconds since last 429)
                            if current_time - self._last_429_time > 60:
                                self._consecutive_429_count = 0
                            self._consecutive_429_count += 1
                            self._last_429_time = current_time

                            # Increase backoff more aggressively when we see multiple consecutive 429s
                            if self._consecutive_429_count > 1:
                                extra_backoff = min(
                                    self._consecutive_429_count * 0.5, 5.0
                                )
                                wait_time = wait_time + extra_backoff

                            # Add jitter to prevent thundering herd
                            jitter = random.uniform(0, wait_time * 0.2)
                            actual_wait = wait_time + jitter
                            self._backoff_until = max(
                                self._backoff_until,
                                current_time + actual_wait,
                            )
                        print(
                            f"  ⚠ Rate limited (429). Retrying in {actual_wait:.1f} seconds... (attempt {attempt + 1}/{self._max_retries})"
                        )

                        time.sleep(actual_wait)
                        wait_time *= 2
                        continue
                # For all other cases (including 5xx), re-raise
                raise

        # Should not reach here, but just in case
        raise Exception("Failed to get response after all retries")
