from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class FileSystemProvider(ABC):
    """Abstract filesystem provider for folder watch connectors."""

    @abstractmethod
    def list_files(self, path: str, *, recursive: bool = False) -> list[dict[str, Any]]:
        """List files under the supplied path."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return whether a path exists."""

    @abstractmethod
    def is_file(self, path: str) -> bool:
        """Return whether a path points to a file."""

    @abstractmethod
    def read_bytes(self, path: str) -> bytes:
        """Read the file contents as bytes."""

    @abstractmethod
    def stat(self, path: str) -> dict[str, Any]:
        """Return metadata for the file."""
