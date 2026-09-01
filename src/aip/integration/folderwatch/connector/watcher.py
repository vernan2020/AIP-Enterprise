from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aip.integration.folderwatch.configuration.folder_config import FolderWatchConfig
from aip.integration.folderwatch.contracts.file_request import FileRequest
from aip.integration.folderwatch.providers.filesystem_provider import FileSystemProvider
from aip.integration.folderwatch.providers.local_filesystem_provider import LocalFileSystemProvider


@dataclass(slots=True)
class FolderWatcher:
    """Generic watcher that scans configured folders and produces file requests."""

    provider: FileSystemProvider = field(default_factory=LocalFileSystemProvider)
    config: FolderWatchConfig = field(default_factory=FolderWatchConfig)
    state: str = "stopped"

    def start(self) -> None:
        self.state = "running"

    def stop(self) -> None:
        self.state = "stopped"

    def scan_once(self) -> list[FileRequest]:
        requests: list[FileRequest] = []
        for folder in self.config.folder_paths:
            for file_info in self.provider.list_files(folder, recursive=self.config.recursive):
                path = str(file_info.get("path", folder))
                filename = str(file_info.get("filename", Path(path).name))
                extension = str(file_info.get("extension") or Path(path).suffix)
                size = int(file_info.get("size", 0))
                if self._matches_filters(path, filename, extension, size):
                    requests.append(
                        FileRequest(path=path, filename=filename, extension=extension, size=size)
                    )
        return requests

    def _matches_filters(self, path: str, filename: str, extension: str, size: int) -> bool:
        if self.config.ignore_hidden and filename.startswith("."):
            return False
        if self.config.ignore_temp and filename.startswith("~"):
            return False
        if extension and self.config.extensions and extension not in self.config.extensions:
            return False
        has_filename_match = not self.config.filename_patterns or any(
            pattern in filename for pattern in self.config.filename_patterns
        )
        has_regex_match = not self.config.regex_patterns or any(
            __import__("re").search(pattern, filename) for pattern in self.config.regex_patterns
        )
        if self.config.filename_patterns or self.config.regex_patterns:
            if not (has_filename_match or has_regex_match):
                return False
        if size < self.config.min_size:
            return False
        if size > self.config.max_size:
            return False
        return True
