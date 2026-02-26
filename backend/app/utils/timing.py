"""Reusable timing tracker for key events and processes."""

import time
from contextlib import contextmanager
from typing import Optional

from app.logging import get_logger

logger = get_logger(__name__)


class TimingTracker:
    """Track elapsed time for named spans with optional logging."""

    def __init__(self, name: str, log_on_exit: bool = True):
        self.name = name
        self.log_on_exit = log_on_exit
        self._start: Optional[float] = None
        self._elapsed_ms: Optional[int] = None

    def start(self) -> "TimingTracker":
        self._start = time.perf_counter()
        self._elapsed_ms = None
        return self

    def stop(self) -> int:
        if self._start is None:
            return 0
        self._elapsed_ms = int((time.perf_counter() - self._start) * 1000)
        if self.log_on_exit:
            logger.info("timing.%s elapsed_ms=%s", self.name, self._elapsed_ms)
        return self._elapsed_ms

    @property
    def elapsed_ms(self) -> Optional[int]:
        if self._elapsed_ms is not None:
            return self._elapsed_ms
        if self._start is None:
            return None
        return int((time.perf_counter() - self._start) * 1000)

    def __enter__(self) -> "TimingTracker":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


@contextmanager
def time_span(name: str, **extra: object):
    """Context manager for timing a block with optional extra log fields."""
    t = TimingTracker(name, log_on_exit=False)
    t.start()
    try:
        yield t
    finally:
        elapsed = t.stop()
        parts = [f"elapsed_ms={elapsed}"] + [f"{k}={v}" for k, v in extra.items()]
        logger.info("timing.%s %s", name, " ".join(parts))
