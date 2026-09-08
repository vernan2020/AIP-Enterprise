from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True, slots=True)
class StartupTimingSnapshot:
    """Immutable startup latency snapshot expressed in milliseconds."""

    total_ms: float
    stages_ms: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "total_ms": self.total_ms,
            "stages_ms": dict(self.stages_ms),
        }


class StartupTimer:
    """Lightweight monotonic timer for the desktop cold-start path."""

    def __init__(self, *, started_at: float | None = None) -> None:
        self._started_at = started_at if started_at is not None else time.perf_counter()
        self._stages_ms: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        label = name.strip()
        if not label:
            raise ValueError("startup stage name must not be blank")
        started = time.perf_counter()
        try:
            yield
        finally:
            self._stages_ms[label] = (time.perf_counter() - started) * 1000.0

    def snapshot(self) -> StartupTimingSnapshot:
        return StartupTimingSnapshot(
            total_ms=(time.perf_counter() - self._started_at) * 1000.0,
            stages_ms=dict(self._stages_ms),
        )

    @staticmethod
    def profile_enabled() -> bool:
        return os.getenv("AIP_PROFILE_STARTUP", "").strip().casefold() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def format_snapshot(snapshot: StartupTimingSnapshot) -> str:
        lines = ["AIP STARTUP PROFILE"]
        for name, duration_ms in snapshot.stages_ms.items():
            lines.append(f" - {name}: {duration_ms:.2f} ms")
        lines.append(f" - total_to_window_ready: {snapshot.total_ms:.2f} ms")
        return "\n".join(lines)
