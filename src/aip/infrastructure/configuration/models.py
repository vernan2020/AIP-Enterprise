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


class PowerBISemanticRouteConfiguration(BaseModel):
    """Non-secret deployment configuration for one Power BI semantic route."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    dataset_id: str = Field(min_length=1)
    workspace_id: str | None = Field(default=None, min_length=1)
    authentication_profile_key: str = Field(min_length=1)


class PowerBIAuthenticationProfileConfiguration(BaseModel):
    """Non-secret Microsoft Entra public-client profile for Power BI delegated access."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    client_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    scopes: tuple[str, ...] = (
        "https://analysis.windows.net/powerbi/api/Dataset.Read.All",
    )


class IRRBBSettings(BaseModel):
    """Optional deployment configuration used by governed IRRBB physical adapters."""

    model_config = ConfigDict(frozen=True)
    power_bi_semantic_routes: dict[str, PowerBISemanticRouteConfiguration] = Field(
        default_factory=dict
    )
    power_bi_authentication_profiles: dict[
        str, PowerBIAuthenticationProfileConfiguration
    ] = Field(default_factory=dict)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    irrbb: IRRBBSettings = Field(default_factory=IRRBBSettings)
