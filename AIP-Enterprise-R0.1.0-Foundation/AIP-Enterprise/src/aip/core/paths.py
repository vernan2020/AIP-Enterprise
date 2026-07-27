from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    root: Path
    config: Path
    database: Path
    logs: Path
    data: Path

    @classmethod
    def discover(cls) -> "ProjectPaths":
        root = Path(__file__).resolve().parents[3]
        return cls(root, root / "config", root / "database", root / "logs", root / "data")

    def ensure(self) -> None:
        for directory in (
            self.config,
            self.database,
            self.logs,
            self.data / "input",
            self.data / "processed",
            self.data / "exports",
        ):
            directory.mkdir(parents=True, exist_ok=True)
