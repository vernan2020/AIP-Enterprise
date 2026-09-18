from __future__ import annotations

import io
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pyarrow as pa

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceDescriptor
from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelColumnMetadata,
    IRRBBSemanticModelInspectionSnapshot,
    IRRBBSemanticModelMeasureMetadata,
    IRRBBSemanticModelRelationshipMetadata,
    IRRBBSemanticModelSchemaFreshness,
    IRRBBSemanticModelTableMetadata,
)
from aip.product.configured.irrbb.power_bi_semantic_route import PowerBISemanticModelRoute

_TABLES_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.TABLES(),
    "Name", [Name],
    "IsHidden", [IsHidden]
)
ORDER BY [Name]
"""

_COLUMNS_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.COLUMNS(),
    "Table", [Table],
    "Name", [Name],
    "DataType", [DataType],
    "IsHidden", [IsHidden]
)
ORDER BY [Table], [Name]
"""

_MEASURES_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.MEASURES(),
    "Table", [Table],
    "Name", [Name],
    "IsHidden", [IsHidden]
)
ORDER BY [Table], [Name]
"""

_RELATIONSHIPS_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.RELATIONSHIPS(),
    "Name", [Name],
    "FromTable", [FromTable],
    "FromColumn", [FromColumn],
    "ToTable", [ToTable],
    "ToColumn", [ToColumn],
    "IsActive", [IsActive],
    "CrossFilteringBehavior", [CrossFilteringBehavior],
    "FromCardinality", [FromCardinality],
    "ToCardinality", [ToCardinality]
)
ORDER BY [FromTable], [FromColumn], [ToTable], [ToColumn]
"""


class PowerBIAccessTokenProvider(Protocol):
    """Resolve a short-lived Power BI bearer token from an opaque profile key."""

    def require_access_token(self, *, authentication_profile_key: str) -> str: ...


class PowerBIArrowMetadataTransport(Protocol):
    """Provider I/O boundary for identity JSON and Arrow metadata queries."""

    def get_json(self, *, url: str, access_token: str) -> Mapping[str, Any]: ...

    def post_arrow(
        self,
        *,
        url: str,
        access_token: str,
        payload: Mapping[str, Any],
    ) -> bytes: ...


@dataclass(frozen=True, slots=True)
class UrllibPowerBIArrowMetadataTransport:
    """Minimal stdlib HTTP adapter for Power BI metadata-only inspection."""

    timeout_seconds: float = 30.0

    def get_json(self, *, url: str, access_token: str) -> Mapping[str, Any]:
        request = Request(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        body = self._read_response(request=request, url=url)
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Power BI dataset metadata response was not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Power BI dataset metadata response must be a JSON object")
        return decoded

    def post_arrow(
        self,
        *,
        url: str,
        access_token: str,
        payload: Mapping[str, Any],
    ) -> bytes:
        body = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        return self._read_response(request=request, url=url)

    def _read_response(self, *, request: Request, url: str) -> bytes:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                return response.read()
        except HTTPError as exc:
            raise RuntimeError(
                f"Power BI metadata request failed with HTTP {exc.code}: {url}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Power BI metadata request failed: {url}") from exc


@dataclass(slots=True)
class PowerBIArrowSemanticMetadataSnapshotFetcher:
    """Fetch governed Power BI semantic-model metadata without row-data extraction."""

    access_token_provider: PowerBIAccessTokenProvider
    transport: PowerBIArrowMetadataTransport
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def fetch_metadata(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
        route: PowerBISemanticModelRoute,
    ) -> IRRBBSemanticModelInspectionSnapshot:
        token = self._require_token(
            self.access_token_provider.require_access_token(
                authentication_profile_key=route.authentication_profile_key
            )
        )
        dataset = self.transport.get_json(
            url=route.dataset_metadata_url,
            access_token=token,
        )
        provider_model_name = self._validate_dataset_identity(
            dataset=dataset,
            source=source,
            route=route,
        )

        table_rows = self._execute_metadata_query(route=route, token=token, query=_TABLES_QUERY)
        column_rows = self._execute_metadata_query(route=route, token=token, query=_COLUMNS_QUERY)
        measure_rows = self._execute_metadata_query(
            route=route,
            token=token,
            query=_MEASURES_QUERY,
        )
        relationship_rows = self._execute_metadata_query(
            route=route,
            token=token,
            query=_RELATIONSHIPS_QUERY,
        )

        tables = self._build_tables(
            table_rows=table_rows,
            column_rows=column_rows,
            measure_rows=measure_rows,
        )
        relationships = self._build_relationships(relationship_rows)

        observed_at = self.clock()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("Power BI metadata fetcher clock must return timezone-aware datetime")

        workspace_reference = (
            "powerbi://my-workspace"
            if route.workspace_id is None
            else f"powerbi://workspace/{route.workspace_id}"
        )
        return IRRBBSemanticModelInspectionSnapshot(
            source_id=source.source_id,
            logical_name=source.logical_name,
            provider_workspace_reference=workspace_reference,
            provider_model_reference=f"powerbi://dataset/{route.dataset_id}",
            provider_model_name=provider_model_name,
            inspection_method="powerbi-rest-execute-dax-queries-arrow-info-view",
            observed_at=observed_at,
            schema_freshness=IRRBBSemanticModelSchemaFreshness.CURRENT,
            row_data_included=False,
            expressions_included=False,
            tables=tables,
            relationships=relationships,
        )

    def _execute_metadata_query(
        self,
        *,
        route: PowerBISemanticModelRoute,
        token: str,
        query: str,
    ) -> list[dict[str, Any]]:
        payload = {"query": query}
        body = self.transport.post_arrow(
            url=route.execute_dax_queries_url,
            access_token=token,
            payload=payload,
        )
        try:
            table = pa.ipc.open_stream(io.BytesIO(body)).read_all()
        except (pa.ArrowInvalid, pa.ArrowIOError, OSError) as exc:
            raise RuntimeError("Power BI metadata query returned invalid Arrow IPC") from exc
        rows = table.to_pylist()
        if not isinstance(rows, list):
            raise RuntimeError("Power BI Arrow metadata query returned an invalid row collection")
        return [dict(row) for row in rows]

    @staticmethod
    def _require_token(token: str) -> str:
        if not isinstance(token, str) or not token or token != token.strip():
            raise ValueError("Power BI access token provider returned an invalid token")
        return token

    @staticmethod
    def _validate_dataset_identity(
        *,
        dataset: Mapping[str, Any],
        source: IRRBBPhysicalSourceDescriptor,
        route: PowerBISemanticModelRoute,
    ) -> str:
        provider_id = dataset.get("id")
        provider_name = dataset.get("name")
        if provider_id != str(route.dataset_id):
            raise ValueError("Power BI dataset metadata returned a different dataset id")
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("Power BI dataset metadata did not return a model name")
        if provider_name != source.logical_name:
            raise ValueError(
                "Power BI dataset name does not match governed physical source logical_name"
            )
        return provider_name

    @staticmethod
    def _build_tables(
        *,
        table_rows: list[dict[str, Any]],
        column_rows: list[dict[str, Any]],
        measure_rows: list[dict[str, Any]],
    ) -> tuple[IRRBBSemanticModelTableMetadata, ...]:
        columns_by_table: dict[str, list[IRRBBSemanticModelColumnMetadata]] = {}
        for row in column_rows:
            table_name = _require_row_text(row, "Table")
            columns_by_table.setdefault(table_name, []).append(
                IRRBBSemanticModelColumnMetadata(
                    name=_require_row_text(row, "Name"),
                    data_type=_require_row_text(row, "DataType"),
                    is_hidden=_optional_bool(row.get("IsHidden")),
                )
            )

        measures_by_table: dict[str, list[IRRBBSemanticModelMeasureMetadata]] = {}
        for row in measure_rows:
            table_name = _require_row_text(row, "Table")
            measures_by_table.setdefault(table_name, []).append(
                IRRBBSemanticModelMeasureMetadata(
                    name=_require_row_text(row, "Name"),
                    is_hidden=_optional_bool(row.get("IsHidden")),
                )
            )

        tables: list[IRRBBSemanticModelTableMetadata] = []
        for row in table_rows:
            table_name = _require_row_text(row, "Name")
            columns = tuple(columns_by_table.pop(table_name, ()))
            if not columns:
                raise ValueError(
                    f"Power BI semantic table {table_name!r} exposed no columns; refusing partial evidence"
                )
            tables.append(
                IRRBBSemanticModelTableMetadata(
                    name=table_name,
                    is_hidden=_optional_bool(row.get("IsHidden")),
                    columns=columns,
                    measures=tuple(measures_by_table.pop(table_name, ())),
                )
            )

        if columns_by_table:
            raise ValueError("Power BI column metadata references an unknown table")
        if measures_by_table:
            raise ValueError("Power BI measure metadata references an unknown table")
        if not tables:
            raise ValueError("Power BI metadata query returned no semantic tables")
        return tuple(tables)

    @staticmethod
    def _build_relationships(
        rows: list[dict[str, Any]],
    ) -> tuple[IRRBBSemanticModelRelationshipMetadata, ...]:
        return tuple(
            IRRBBSemanticModelRelationshipMetadata(
                name=_optional_text(row.get("Name")),
                from_table=_require_row_text(row, "FromTable"),
                from_column=_require_row_text(row, "FromColumn"),
                to_table=_require_row_text(row, "ToTable"),
                to_column=_require_row_text(row, "ToColumn"),
                is_active=_optional_bool(row.get("IsActive")),
                cross_filter_direction=_optional_text(row.get("CrossFilteringBehavior")),
                from_cardinality=_optional_text(row.get("FromCardinality")),
                to_cardinality=_optional_text(row.get("ToCardinality")),
            )
            for row in rows
        )


def _require_row_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Power BI metadata row requires nonblank {key}")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Power BI metadata optional text value must be nonblank when present")
    return value


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError("Power BI metadata boolean value must be bool when present")
    return value
