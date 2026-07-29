from __future__ import annotations

from pathlib import Path
from typing import Any

from aip.integration.folderwatch.providers.filesystem_provider import FileSystemProvider


class LocalFileSystemProvider(FileSystemProvider):
    """Local filesystem provider using Python’s pathlib."""

    def list_files(self, path: str, *, recursive: bool = False) -> list[dict[str, Any]]:
        root = Path(path)
        if not root.exists():
            return []
        if recursive:
            candidates = [p for p in root.rglob("*") if p.is_file()]
        else:
            candidates = [p for p in root.iterdir() if p.is_file()]
        return [
            {
                "path": str(p),
                "filename": p.name,
                "extension": p.suffix,
                "size": p.stat().st_size,
            }
            for p in candidates
        ]

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def is_file(self, path: str) -> bool:
        return Path(path).is_file()

    def read_bytes(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def stat(self, path: str) -> dict[str, Any]:
        file_path = Path(path)
        return {"size": file_path.stat().st_size, "modified": file_path.stat().st_mtime}
