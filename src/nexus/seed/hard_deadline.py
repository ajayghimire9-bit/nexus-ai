"""External wall-clock deadline over an owned runtime process."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class HardDeadline:
    def __init__(self, seconds: float):
        if seconds <= 0:
            raise ValueError("deadline_must_be_positive")
        self.seconds = float(seconds)
        self.start = time.monotonic()
        self.end = self.start + self.seconds
        self._timer: threading.Timer | None = None
        self._runtime = None
        self.fired = False
        self.cancel_reason = None

    def remaining(self) -> float:
        return max(0.0, self.end - time.monotonic())

    def expired(self) -> bool:
        return time.monotonic() >= self.end or self.fired

    def arm(self, runtime) -> None:
        self._runtime = runtime
        delay = self.remaining()
        self._timer = threading.Timer(delay, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self) -> None:
        self.fired = True
        self.cancel_reason = "hard_deadline"
        runtime = self._runtime
        if runtime is not None and hasattr(runtime, "close"):
            try:
                runtime.close()
            except Exception:
                pass

    def check(self) -> None:
        if self.expired():
            raise TimeoutError("hard_deadline")

    def disarm(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def wrap_call(self, fn: Callable[..., Any], *args, **kwargs):
        self.check()
        return fn(*args, **kwargs)
