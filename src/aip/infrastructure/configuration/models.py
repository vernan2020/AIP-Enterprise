from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ApplicationSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = "AIP Enterprise"
    organization: str = "Coopealianza R.L."
    environment: str = "development"
    debug: bool = True
    window_width: int = Field(default=1440, ge=1024)
    window_height: int = Field(default=900, ge=720)


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    engine: str = "duckdb"
    path: Path = Path("database/aip.duckdb")
    read_only: bool = False


class LoggingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    level: str = "INFO"
    directory: Path = Path("logs")
    application_filename: str = "aip.log"
    audit_filename: str = "audit.jsonl"
    rotation: str = "25 MB"
    retention: str = "90 days"
    compression: str | None = "zip"
    serialize: bool = False


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
