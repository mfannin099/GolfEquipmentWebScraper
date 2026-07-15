"""Simple client-side throttle so scrapers don't hammer a site."""

import time


class RateLimiter:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last_call = None

    def wait(self):
        if self._last_call is not None:
            remaining = self.min_interval - (time.monotonic() - self._last_call)
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()
