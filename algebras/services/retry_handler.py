"""
Retry handler with exponential backoff for API requests.
"""

import threading
import time
import random
import requests
from typing import Callable, Optional

from algebras.services.rate_limiter import RateLimiter

# Gateway errors and unavailability: the request may succeed when sent again.
# A 500 is an application error and is not retried.
TRANSIENT_STATUS_CODES = frozenset({502, 503, 504})


class RetryHandler:
    """Thread-safe retry handler with exponential backoff.

    429 responses are retried with a backoff shared across parallel batches.
    502/503/504 responses and connection errors or timeouts are retried per
    call with their own, longer backoff. Other errors are raised at once.
    """

    def __init__(
        self,
        rate_limiter: RateLimiter,
        max_retries: int = 5,
        initial_wait: float = 1.0,
        transient_retries: int = 3,
        transient_initial_wait: float = 2.0,
        transient_max_wait: float = 30.0,
    ):
        """
        Initialize RetryHandler.

        Args:
            rate_limiter: RateLimiter instance for coordinating rate limits
            max_retries: Maximum number of retries for 429 errors (default: 5)
            initial_wait: Initial wait time in seconds for 429 errors (default: 1.0)
            transient_retries: Maximum number of retries for 502/503/504 and
                connection errors (default: 3)
            transient_initial_wait: Initial wait in seconds before retrying a
                transient error; tripled on each retry (default: 2.0)
            transient_max_wait: Longest single wait for a transient error,
                including a server's Retry-After (default: 30.0)
        """
        self._rate_limiter = rate_limiter
        self._max_retries = max_retries
        self._initial_wait = initial_wait
        self._transient_retries = transient_retries
        self._transient_initial_wait = transient_initial_wait
        self._transient_max_wait = transient_max_wait

        # Shared state for coordinating retries across parallel batches
        self._lock = threading.Lock()
        self._backoff_until = 0.0  # Timestamp until which we should back off
        self._consecutive_429_count = 0  # Track consecutive 429 errors across all batches
        self._last_429_time = 0.0  # Timestamp of last 429 error

    def execute_with_retry(
        self, api_call_func: Callable[[], requests.Response]
    ) -> requests.Response:
        """
        Execute an API call, retrying 429, 502/503/504 and connection errors.

        Args:
            api_call_func: Callable that makes the API request and returns a response

        Returns:
            Response object from the API call

        Raises:
            Exception: For other 5xx errors and request errors, or once the
                retries for 429 or transient errors are used up
        """
        wait_time = self._initial_wait
        rate_limit_retries = 0
        transient_retries = 0

        while True:
            self._wait_for_shared_backoff()
            self._rate_limiter.wait_if_needed()

            response: Optional[requests.Response] = None
            try:
                response = api_call_func()
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                failure = f"Request failed: {str(e)}"
                reason = f"Connection error ({type(e).__name__})"
            except requests.exceptions.RequestException as e:
                raise Exception(f"Request failed: {str(e)}")

            if response is not None:
                status_code = response.status_code

                if status_code == 429:
                    if rate_limit_retries >= self._max_retries:
                        raise Exception(
                            f"Error from Algebras AI API: 429 Too Many Requests - {response.text}"
                        )
                    rate_limit_retries += 1
                    actual_wait = self._register_429(wait_time)
                    print(
                        f"  ⚠ Rate limited (429). Retrying in {actual_wait:.1f} seconds... (attempt {rate_limit_retries}/{self._max_retries})"
                    )
                    time.sleep(actual_wait)
                    wait_time *= 2  # Exponential backoff
                    continue

                if 500 <= status_code < 600:
                    failure = f"Error from Algebras AI API: {status_code} - {response.text}"
                    if status_code not in TRANSIENT_STATUS_CODES:
                        raise Exception(failure)
                    reason = f"Server error {status_code}"
                else:
                    if status_code == 200:
                        with self._lock:
                            self._consecutive_429_count = 0
                    return response

            # Transient failure: 502/503/504 or a connection error.
            if transient_retries >= self._transient_retries:
                raise Exception(failure)
            delay = self._transient_delay(transient_retries, response)
            transient_retries += 1
            print(
                f"  ⚠ {reason}. Retrying in {delay:.1f} seconds... (attempt {transient_retries}/{self._transient_retries})"
            )
            time.sleep(delay)

    def _wait_for_shared_backoff(self) -> None:
        """Wait out a backoff another batch set after a 429."""
        with self._lock:
            current_time = time.time()
            if self._backoff_until > current_time:
                wait_needed = self._backoff_until - current_time
                print(
                    f"  ⚠ Waiting for shared rate limit backoff: {wait_needed:.1f} seconds..."
                )
                time.sleep(wait_needed)

    def _register_429(self, wait_time: float) -> float:
        """Record a 429 in the shared state; return how long this call waits."""
        with self._lock:
            current_time = time.time()

            # Track consecutive 429 errors (reset if more than 60 seconds since last 429)
            if current_time - self._last_429_time > 60:
                self._consecutive_429_count = 0
            self._consecutive_429_count += 1
            self._last_429_time = current_time

            # Back off harder when several batches hit 429 at once:
            # 0.5s extra per consecutive 429, capped at 5s.
            if self._consecutive_429_count > 1:
                wait_time += min(self._consecutive_429_count * 0.5, 5.0)

            # Jitter (0-20%) prevents a thundering herd
            actual_wait = wait_time + random.uniform(0, wait_time * 0.2)
            self._backoff_until = max(self._backoff_until, current_time + actual_wait)
            return actual_wait

    def _transient_delay(
        self, retry_index: int, response: Optional[requests.Response]
    ) -> float:
        """Backoff before retry number retry_index + 1 of a transient error."""
        delay = self._transient_initial_wait * (3**retry_index)
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            delay = retry_after
        delay = min(delay, self._transient_max_wait)
        return delay + random.uniform(0, delay * 0.2)


def _retry_after_seconds(response: Optional[requests.Response]) -> Optional[float]:
    """A numeric Retry-After header in seconds, if the response has one."""
    if response is None:
        return None
    try:
        value = response.headers.get("Retry-After")
        return max(float(value), 0.0) if value is not None else None
    except (AttributeError, TypeError, ValueError):
        return None
