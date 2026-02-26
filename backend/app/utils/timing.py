"""Reusable timing tracker for key events and processes."""

import time
from contextlib import contextmanager
from typing import Optional

from app.logging import get_logger

logger = get_logger(__name__)

# Prefix for all timing logs so they stand out and are easy to grep
_TIMING_PREFIX = "[TIMING]"


def _format_duration(ms: int) -> str:
    """Return human-readable duration: e.g. 12500 -> '12.5s', 750 -> '750ms'."""
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"


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
            logger.info(
                "%s %s elapsed_ms=%s (%s)",
                _TIMING_PREFIX,
                self.name,
                self._elapsed_ms,
                _format_duration(self._elapsed_ms),
            )
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
        parts = [f"elapsed_ms={elapsed}", f"({_format_duration(elapsed)})"] + [
            f"{k}={v}" for k, v in extra.items()
        ]
        logger.info("%s %s %s", _TIMING_PREFIX, name, " ".join(parts))
