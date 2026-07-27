from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError

from aip.infrastructure.configuration.exceptions import ConfigurationError
from aip.infrastructure.configuration.models import Settings


class ConfigurationManager:
    def __init__(self, config_directory: Path) -> None:
        self._config_directory = config_directory
        self._settings: Settings | None = None

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            raise ConfigurationError("La configuración aún no ha sido cargada.")
        return self._settings

    def load(self) -> Settings:
        merged: dict[str, Any] = {}
        for filename in ("application.yaml", "database.yaml", "logging.yaml"):
            path = self._config_directory / filename
            if not path.exists():
                raise ConfigurationError(f"No existe el archivo requerido: {path}")
            try:
                content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise ConfigurationError(f"YAML inválido en {path}: {exc}") from exc
            if not isinstance(content, dict):
                raise ConfigurationError(f"El archivo {path} debe contener un objeto YAML.")
            merged.update(content)
        try:
            self._settings = Settings.model_validate(merged)
        except ValidationError as exc:
            raise ConfigurationError(f"Configuración inválida: {exc}") from exc
        return self._settings
