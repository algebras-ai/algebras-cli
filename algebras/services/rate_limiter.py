"""
Rate limiter for API requests using sliding window approach.
"""

import threading
import time
from typing import List


class RateLimiter:
    """Thread-safe rate limiter using sliding window approach."""

    def __init__(self, max_requests_per_minute: int = 30):
        """
        Initialize RateLimiter.

        Args:
            max_requests_per_minute: Maximum number of requests allowed per minute (default: 30)
        """
        self._lock = threading.Lock()
        self._max_requests_per_minute = max_requests_per_minute
        self._request_timestamps: List[float] = []

    def wait_if_needed(self) -> None:
        """
        Wait if necessary to respect the rate limit.
        Uses a sliding window approach to track requests in the last 60 seconds.
        Automatically records the request timestamp after waiting.
        """
        with self._lock:
            current_time = time.time()

            # Remove timestamps older than 60 seconds
            self._request_timestamps = [
                ts for ts in self._request_timestamps if current_time - ts < 60.0
            ]

            # If we're at the limit, wait until the oldest request is more than 60 seconds old
            if len(self._request_timestamps) >= self._max_requests_per_minute:
                oldest_timestamp = min(self._request_timestamps)
                wait_time = (
                    60.0 - (current_time - oldest_timestamp) + 0.1
                )  # Add 0.1s buffer
                if wait_time > 0:
                    print(
                        f"  ⚠ Rate limit: {len(self._request_timestamps)}/{self._max_requests_per_minute} requests in last minute. Waiting {wait_time:.1f} seconds..."
                    )
                    time.sleep(wait_time)
                    # Update current time after waiting
                    current_time = time.time()
                    # Clean up old timestamps again
                    self._request_timestamps = [
                        ts
                        for ts in self._request_timestamps
                        if current_time - ts < 60.0
                    ]

            # Record this request timestamp
            self._request_timestamps.append(current_time)

    def record_request(self) -> None:
        """
        Record a request timestamp without waiting.
        Useful when you need to record a request that was already rate-limited elsewhere.
        """
        with self._lock:
            current_time = time.time()
            # Clean up old timestamps
            self._request_timestamps = [
                ts for ts in self._request_timestamps if current_time - ts < 60.0
            ]
            self._request_timestamps.append(current_time)
