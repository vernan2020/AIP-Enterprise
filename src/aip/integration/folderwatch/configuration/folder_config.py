from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FolderWatchConfig:
    """Configuration for a folder watch connector."""

    folder_paths: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    filename_patterns: list[str] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    recursive: bool = False
    min_size: int = 0
    max_size: int = 1024 * 1024
    ignore_hidden: bool = True
    ignore_temp: bool = True
    poll_interval_seconds: float = 5.0
    restart_on_error: bool = True

    def __post_init__(self) -> None:
        if not self.folder_paths:
            raise ValueError("folder_paths is required")
        if self.max_size < self.min_size:
            raise ValueError("max_size must be greater than or equal to min_size")
        if self.max_size <= 0:
            raise ValueError("max_size must be greater than zero")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")
        if self.min_size < 0:
            raise ValueError("min_size cannot be negative")

    def __repr__(self) -> str:
        return (
            f"FolderWatchConfig(folder_paths={self.folder_paths!r}, extensions={self.extensions!r}, "
            f"recursive={self.recursive!r}, min_size={self.min_size!r}, max_size={self.max_size!r})"
        )
