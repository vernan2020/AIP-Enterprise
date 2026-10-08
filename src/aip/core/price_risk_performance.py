from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from time import perf_counter

_LOGGER = logging.getLogger("aip.price_risk.performance")
_LOCK = Lock()


def record_stage_duration(stage: str, started: float) -> None:
    """Persist stage timings only during an explicitly enabled local diagnosis.

    No portfolio content or customer identifiers are recorded. Logging failures
    must never interrupt certified risk calculations.
    """
    if os.getenv("AIP_PRICE_RISK_PROFILE", "").strip().lower() not in {"1", "true", "yes"}:
        return

    try:
        with _LOCK:
            if not _LOGGER.handlers:
                log_path = Path.cwd() / "logs" / "price_risk_performance.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(
                    log_path,
                    maxBytes=1_000_000,
                    backupCount=2,
                    encoding="utf-8",
                )
                handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
                _LOGGER.addHandler(handler)
                _LOGGER.setLevel(logging.INFO)
                _LOGGER.propagate = False
            _LOGGER.info(
                "stage=%s duration_ms=%.1f",
                stage,
                (perf_counter() - started) * 1000,
            )
    except OSError:
        # Profiling must never become a dependency of the risk engine.
        return
