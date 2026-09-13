from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceDescriptor


class IRRBBSemanticModelSchemaFreshness(str, Enum):
    """Provider-reported freshness of inspected semantic-model schema metadata."""

    CURRENT = "CURRENT"
    MAY_BE_STALE = "MAY_BE_STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class IRRBBSemanticModelColumnMetadata:
    """Source-neutral physical column metadata without RTILB business meaning."""

    name: str
    data_type: str
    is_hidden: bool | None

    def __post_init__(self) -> None:
        _require_text("column name", self.name)
        _require_text("column data_type", self.data_type)


@dataclass(frozen=True, slots=True)
class IRRBBSemanticModelMeasureMetadata:
    """Measure identity only; expressions are intentionally excluded from evidence."""

    name: str
    is_hidden: bool | None

    def __post_init__(self) -> None:
        _require_text("measure name", self.name)


@dataclass(frozen=True, slots=True)
class IRRBBSemanticModelTableMetadata:
    """One physical semantic-model table and its discoverable schema metadata."""

    name: str
    is_hidden: bool | None
    columns: tuple[IRRBBSemanticModelColumnMetadata, ...]
    measures: tuple[IRRBBSemanticModelMeasureMetadata, ...]

    def __post_init__(self) -> None:
        _require_text("table name", self.name)
        if not self.columns:
            raise ValueError("semantic-model table must expose at least one column")
        _require_unique_names("semantic-model columns", tuple(item.name for item in self.columns))
        _require_unique_names("semantic-model measures", tuple(item.name for item in self.measures))


@dataclass(frozen=True, slots=True)
class IRRBBSemanticModelRelationshipMetadata:
    """Physical relationship metadata with no inferred financial interpretation."""

    name: str | None
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    is_active: bool | None
    cross_filter_direction: str | None
    from_cardinality: str | None
    to_cardinality: str | None

    def __post_init__(self) -> None:
        _validate_optional_text("relationship name", self.name)
        _require_text("relationship from_table", self.from_table)
        _require_text("relationship from_column", self.from_column)
        _require_text("relationship to_table", self.to_table)
        _require_text("relationship to_column", self.to_column)
        _validate_optional_text("relationship cross_filter_direction", self.cross_filter_direction)
        _validate_optional_text("relationship from_cardinality", self.from_cardinality)
        _validate_optional_text("relationship to_cardinality", self.to_cardinality)


@dataclass(frozen=True, slots=True)
class IRRBBSemanticModelInspectionSnapshot:
    """Auditable metadata-only evidence returned by a semantic-model inspector.

    Provider workspace/model references are runtime-observed opaque identifiers. They
    are evidence, not source configuration, and must never be hard-coded by callers.
    The contract rejects row data and expressions so discovery cannot silently turn
    into contractual-position extraction.
    """

    source_id: str
    logical_name: str
    provider_workspace_reference: str
    provider_model_reference: str
    provider_model_name: str
    inspection_method: str
    observed_at: datetime
    schema_freshness: IRRBBSemanticModelSchemaFreshness
    row_data_included: bool
    expressions_included: bool
    tables: tuple[IRRBBSemanticModelTableMetadata, ...]
    relationships: tuple[IRRBBSemanticModelRelationshipMetadata, ...]

    def __post_init__(self) -> None:
        _require_text("semantic-model source_id", self.source_id)
        _require_text("semantic-model logical_name", self.logical_name)
        _require_text(
            "semantic-model provider_workspace_reference",
            self.provider_workspace_reference,
        )
        _require_text("semantic-model provider_model_reference", self.provider_model_reference)
        _require_text("semantic-model provider_model_name", self.provider_model_name)
        _require_text("semantic-model inspection_method", self.inspection_method)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("semantic-model observed_at must be timezone-aware")
        if self.row_data_included:
            raise ValueError("semantic-model inspection evidence must not contain row data")
        if self.expressions_included:
            raise ValueError("semantic-model inspection evidence must not contain expressions")
        if not self.tables:
            raise ValueError("semantic-model inspection evidence must contain at least one table")

        _require_unique_names("semantic-model tables", tuple(item.name for item in self.tables))
        self._validate_relationships()

    def _validate_relationships(self) -> None:
        tables = {table.name.casefold(): table for table in self.tables}
        seen_relationships: set[tuple[str, str, str, str]] = set()

        for relationship in self.relationships:
            from_table = tables.get(relationship.from_table.casefold())
            to_table = tables.get(relationship.to_table.casefold())
            if from_table is None or to_table is None:
                raise ValueError("semantic-model relationship references an unknown table")

            from_columns = {column.name.casefold() for column in from_table.columns}
            to_columns = {column.name.casefold() for column in to_table.columns}
            if relationship.from_column.casefold() not in from_columns:
                raise ValueError("semantic-model relationship references an unknown from-column")
            if relationship.to_column.casefold() not in to_columns:
                raise ValueError("semantic-model relationship references an unknown to-column")

            key = (
                relationship.from_table.casefold(),
                relationship.from_column.casefold(),
                relationship.to_table.casefold(),
                relationship.to_column.casefold(),
            )
            if key in seen_relationships:
                raise ValueError(
                    "semantic-model inspection evidence contains duplicate relationships"
                )
            seen_relationships.add(key)


class IRRBBSemanticModelMetadataInspector(Protocol):
    """Application port for metadata-only semantic-model discovery.

    Implementations resolve ``source.configuration_key`` outside the application
    layer and may use any institutionally approved provider transport. They must
    return physical metadata only and must not infer RTILB aliases, extract position
    rows, map contracts, or perform financial calculations.
    """

    def inspect(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
    ) -> IRRBBSemanticModelInspectionSnapshot: ...


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _validate_optional_text(field_name: str, value: str | None) -> None:
    if value is not None and not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _require_unique_names(context: str, values: tuple[str, ...]) -> None:
    normalized = tuple(value.casefold() for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{context} must be unique ignoring case")
