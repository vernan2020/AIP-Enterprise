from __future__ import annotations

import importlib.resources as resources
import os
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

    @classmethod
    def discover_from_package(cls) -> "ProjectPaths":
        package_root = Path(os.getcwd())
        return cls(
            package_root,
            package_root / "config",
            package_root / "database",
            package_root / "logs",
            package_root / "data",
        )

    @classmethod
    def default_config_dir(cls) -> Path:
        return Path.home() / ".config" / "aip-enterprise"

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

    def packaged_config_files(self) -> list[tuple[Path, str]]:
        files: list[tuple[Path, str]] = []
        for resource_name in ("application.yaml", "database.yaml", "logging.yaml"):
            resource = resources.files("aip.resources.config").joinpath(resource_name)
            if resource.is_file():
                files.append((Path(str(resource)), resource_name))
        return files
