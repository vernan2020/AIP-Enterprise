from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FileRequest:
    """Generic file request for folder synchronization."""

    path: str
    filename: str
    extension: str
    size: int
    checksum: str | None = None
    timestamp: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "filename": self.filename,
            "extension": self.extension,
            "size": self.size,
            "checksum": self.checksum,
            "timestamp": self.timestamp,
        }
