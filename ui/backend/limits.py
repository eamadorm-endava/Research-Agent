"""Bound per-instance request rates without retaining unbounded user identifiers."""

import time
from collections import OrderedDict, deque
from threading import Lock

from fastapi import HTTPException

from .config import UI_CONFIG


class RequestLimiter:
    """Maintain a bounded sliding window per authenticated user."""

    def __init__(self):
        self.windows = OrderedDict()
        self.lock = Lock()

    def check(self, user: str) -> None:
        """Reject excess requests before any billable agent or OAuth operation."""
        now = time.monotonic()
        with self.lock:
            window = self.windows.setdefault(user, deque())
            self.windows.move_to_end(user)
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= UI_CONFIG.REQUESTS_PER_MINUTE:
                raise HTTPException(
                    429, "Too many requests", headers={"Retry-After": "60"}
                )
            window.append(now)
            while len(self.windows) > 4096:
                self.windows.popitem(last=False)


limiter = RequestLimiter()
