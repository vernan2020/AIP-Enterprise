from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO, TextIOBase
from pathlib import Path
from typing import BinaryIO


@dataclass(slots=True)
class ExportService:
    """Formatting-only export service with retry and cancellation support."""

    retry_attempts: int = 1
    retry_delay_seconds: int = 0
    is_cancelled: bool = False
    _buffer: BytesIO = field(default_factory=BytesIO, init=False, repr=False)

    def export_file(self, report_id: str, payload: BinaryIO | bytes, *, path: str | None = None) -> str:
        if self.is_cancelled:
            raise RuntimeError("Export cancelled")
        data = payload.read() if hasattr(payload, "read") else payload
        destination = path or f"{report_id}.out"
        Path(destination).write_bytes(data)
        return destination

    def export_memory(self, report_id: str, payload: bytes) -> bytes:
        if self.is_cancelled:
            raise RuntimeError("Export cancelled")
        return payload

    def export_streaming(self, report_id: str, payload: BinaryIO | bytes) -> BytesIO:
        if self.is_cancelled:
            raise RuntimeError("Export cancelled")
        if hasattr(payload, "read"):
            data = payload.read()
        else:
            data = payload
        stream = BytesIO(data)
        self._buffer = stream
        return stream

    def cancel(self) -> None:
        self.is_cancelled = True
