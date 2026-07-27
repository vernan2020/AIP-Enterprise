from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
from loguru import logger

from aip.infrastructure.configuration.models import LoggingSettings
from aip.infrastructure.logging.context import current_context


class LoggingManager:
    def __init__(self, settings: LoggingSettings, project_root: Path) -> None:
        self._settings = settings
        self._project_root = project_root
        self._configured = False

    def configure(self) -> None:
        log_dir = self._project_root / self._settings.directory
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.remove()
        text_format = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
            "{extra[component]:<14} | {extra[run_id]} | {message}"
        )
        base = logger.bind(component="SYSTEM", **current_context())
        base.add(sys.stderr, level=self._settings.level, format=text_format, colorize=True, enqueue=True)
        base.add(
            log_dir / self._settings.application_filename,
            level=self._settings.level,
            format=text_format,
            rotation=self._settings.rotation,
            retention=self._settings.retention,
            compression=self._settings.compression,
            enqueue=True,
            encoding="utf-8",
        )
        base.add(
            log_dir / self._settings.audit_filename,
            level="INFO",
            filter=lambda record: record["extra"].get("audit") is True,
            serialize=True,
            rotation=self._settings.rotation,
            retention=self._settings.retention,
            compression=self._settings.compression,
            enqueue=True,
            encoding="utf-8",
        )
        self._configured = True

    def bind(self, *, component: str, **extra: Any):
        if not self._configured:
            raise RuntimeError("LoggingManager no configurado.")
        return logger.bind(component=component, **current_context(), **extra)
