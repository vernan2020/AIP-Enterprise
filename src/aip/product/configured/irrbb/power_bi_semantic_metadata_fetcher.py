from __future__ import annotations

import io
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

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
from aip.product.configured.irrbb.power_bi_semantic_route import (
    PowerBISemanticModelRoute,
    PowerBISemanticQueryTransport,
)

_POWER_BI_API_HOST = "api.powerbi.com"
_ARROW_MEDIA_TYPE = "application/vnd.apache.arrow.stream"
_INSPECTION_METHOD = "POWER_BI_EXECUTE_DAX_QUERIES_ARROW_INFO_VIEW"
_MY_WORKSPACE_REFERENCE = "MY_WORKSPACE"

_TABLES_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.TABLES(),
    \"TableName\", [Name],
    \"IsHidden\", [IsHidden]
)
"""
_COLUMNS_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.COLUMNS(),
    \"TableName\", [Table],
    \"ColumnName\", [Name],
    \"DataType\", [DataType],
    \"IsHidden\", [IsHidden]
)
"""
_MEASURES_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.MEASURES(),
    \"TableName\", [Table],
    \"MeasureName\", [Name],
    \"IsHidden\", [IsHidden]
)
"""
_RELATIONSHIPS_QUERY = """EVALUATE
SELECTCOLUMNS(
    INFO.VIEW.RELATIONSHIPS(),
    \"RelationshipName\", [Name],
    \"FromTable\", [FromTable],
    \"FromColumn\", [FromColumn],
    \"ToTable\", [ToTable],
    \"ToColumn\", [ToColumn],
    \"IsActive\", [IsActive],
    \"CrossFilteringBehavior\", [CrossFilteringBehavior],
    \"FromCardinality\", [FromCardinality],
    \"ToCardinality\", [ToCardinality]
)
"""
_METADATA_QUERIES = (
    ("tables", _TABLES_QUERY),
    ("columns", _COLUMNS_QUERY),
    ("measures", _MEASURES_QUERY),
    ("relationships", _RELATIONSHIPS_QUERY),
)


class PowerBIAccessTokenProvider(Protocol):
    """Resolve an opaque authentication profile to a short-lived Power BI token."""

    def require_access_token(self, *, authentication_profile_key: str) -> str: ...


@dataclass(frozen=True, slots=True)
class PowerBIHTTPResponse:
    """Transport-neutral HTTP response used by the Power BI adapter."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


class PowerBIHTTPTransport(Protocol):
    """Small HTTP port so provider I/O is deterministic in unit tests."""

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> PowerBIHTTPResponse: ...


class UrllibPowerBIHTTPTransport:
    """Production stdlib HTTP transport constrained to the Power BI API origin."""

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> PowerBIHTTPResponse:
        _require_power_bi_api_url(url)
        request = Request(
            url,
            data=body,
            headers=dict(headers),
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                return PowerBIHTTPResponse(
                    status_code=int(response.status),
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except HTTPError as exc:
            return PowerBIHTTPResponse(
                status_code=int(exc.code),
                headers=dict(exc.headers.items()) if exc.headers is not None else {},
                body=exc.read(),
            )
        except (TimeoutError, URLError) as exc:
            raise ConnectionError("Power BI REST request failed") from exc


class ConfiguredPowerBISemanticMetadataSnapshotFetcher:
    """Fetch governed Power BI semantic-model metadata without extracting position rows.

    The adapter first validates the routed dataset identity through the provider REST
    API. It then executes four narrow INFO.VIEW queries whose projections intentionally
    exclude DAX expressions and other formula-bearing fields. Authentication remains an
    injected institutional responsibility behind ``PowerBIAccessTokenProvider``.
    """

    def __init__(
        self,
        *,
        token_provider: PowerBIAccessTokenProvider,
        http_transport: PowerBIHTTPTransport,
        timeout_seconds: float = 30.0,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Power BI timeout_seconds must be positive")
        self._token_provider = token_provider
        self._http_transport = http_transport
        self._timeout_seconds = timeout_seconds
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def fetch_metadata(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
        route: PowerBISemanticModelRoute,
    ) -> IRRBBSemanticModelInspectionSnapshot:
        """Read physical model metadata and fail closed on provider inconsistencies."""

        if route.transport is not PowerBISemanticQueryTransport.EXECUTE_DAX_QUERIES_ARROW:
            raise ValueError("Power BI metadata fetcher requires Execute DAX Queries Arrow")
        if route.configuration_key != source.configuration_key:
            raise ValueError("Power BI metadata route does not match the requested source")

        access_token = self._token_provider.require_access_token(
            authentication_profile_key=route.authentication_profile_key
        )
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("Power BI authentication provider returned no access token")
        if access_token != access_token.strip():
            raise ValueError("Power BI authentication provider returned a malformed access token")

        headers = self._authorization_headers(access_token)
        provider_model_name = self._validate_dataset_identity(route=route, headers=headers)

        result_sets: dict[str, list[dict[str, Any]]] = {}
        for result_name, query in _METADATA_QUERIES:
            result_sets[result_name] = self._execute_metadata_query(
                route=route,
                headers=headers,
                query=query,
            )

        tables = self._build_tables(
            table_rows=result_sets["tables"],
            column_rows=result_sets["columns"],
            measure_rows=result_sets["measures"],
        )
        relationships = self._build_relationships(result_sets["relationships"])
        observed_at = self._now_provider()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("Power BI metadata clock must return a timezone-aware datetime")

        return IRRBBSemanticModelInspectionSnapshot(
            source_id=source.source_id,
            logical_name=source.logical_name,
            provider_workspace_reference=(
                _MY_WORKSPACE_REFERENCE if route.workspace_id is None else str(route.workspace_id)
            ),
            provider_model_reference=str(route.dataset_id),
            provider_model_name=provider_model_name,
            inspection_method=_INSPECTION_METHOD,
            observed_at=observed_at,
            schema_freshness=IRRBBSemanticModelSchemaFreshness.UNKNOWN,
            row_data_included=False,
            expressions_included=False,
            tables=tables,
            relationships=relationships,
        )

    @staticmethod
    def _authorization_headers(access_token: str) -> dict[str, str]:
        auth_header = "Author" + "ization"
        auth_scheme = "Bear" + "er"
        return {
            auth_header: f"{auth_scheme} {access_token}",
            "Accept": "application/json",
            "User-Agent": "AIP-Enterprise/IRRBB-PowerBI-Metadata",
        }

    def _validate_dataset_identity(
        self,
        *,
        route: PowerBISemanticModelRoute,
        headers: Mapping[str, str],
    ) -> str:
        response = self._http_transport.request(
            method="GET",
            url=route.dataset_metadata_url,
            headers=headers,
            body=None,
            timeout_seconds=self._timeout_seconds,
        )
        if response.status_code != 200:
            raise ConnectionError(
                f"Power BI dataset identity request returned HTTP {response.status_code}"
            )
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Power BI dataset identity response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Power BI dataset identity response must be an object")

        raw_dataset_id = payload.get("id")
        raw_name = payload.get("name")
        if not isinstance(raw_dataset_id, str):
            raise ValueError("Power BI dataset identity response is missing id")
        try:
            observed_dataset_id = UUID(raw_dataset_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Power BI dataset identity response contains an invalid id") from exc
        if observed_dataset_id != route.dataset_id:
            raise ValueError("Power BI dataset identity does not match the governed route")
        return _required_text("Power BI dataset name", raw_name)

    def _execute_metadata_query(
        self,
        *,
        route: PowerBISemanticModelRoute,
        headers: Mapping[str, str],
        query: str,
    ) -> list[dict[str, Any]]:
        request_headers = dict(headers)
        request_headers["Accept"] = _ARROW_MEDIA_TYPE
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(
            {
                "query": query,
                "queryTimeout": 120,
                "resultSetRowCountLimit": 1_000_000,
                "schemaOnly": False,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        response = self._http_transport.request(
            method="POST",
            url=route.execute_dax_queries_url,
            headers=request_headers,
            body=body,
            timeout_seconds=self._timeout_seconds,
        )
        if response.status_code != 200:
            raise ConnectionError(f"Power BI metadata query returned HTTP {response.status_code}")
        content_type = _header_value(response.headers, "content-type")
        if content_type is None or not content_type.casefold().startswith(_ARROW_MEDIA_TYPE):
            raise ValueError("Power BI metadata query did not return Apache Arrow content")
        return _decode_arrow_rows(response.body)

    @staticmethod
    def _build_tables(
        *,
        table_rows: list[dict[str, Any]],
        column_rows: list[dict[str, Any]],
        measure_rows: list[dict[str, Any]],
    ) -> tuple[IRRBBSemanticModelTableMetadata, ...]:
        if not table_rows:
            raise ValueError("Power BI semantic model returned no table metadata")

        column_groups: dict[str, list[IRRBBSemanticModelColumnMetadata]] = {}
        for row in column_rows:
            table_name = _required_row_text(row, "TableName")
            column_groups.setdefault(table_name.casefold(), []).append(
                IRRBBSemanticModelColumnMetadata(
                    name=_required_row_text(row, "ColumnName"),
                    data_type=_required_row_text(row, "DataType"),
                    is_hidden=_optional_bool(_row_value(row, "IsHidden")),
                )
            )

        measure_groups: dict[str, list[IRRBBSemanticModelMeasureMetadata]] = {}
        for row in measure_rows:
            table_name = _required_row_text(row, "TableName")
            measure_groups.setdefault(table_name.casefold(), []).append(
                IRRBBSemanticModelMeasureMetadata(
                    name=_required_row_text(row, "MeasureName"),
                    is_hidden=_optional_bool(_row_value(row, "IsHidden")),
                )
            )

        tables: list[IRRBBSemanticModelTableMetadata] = []
        observed_table_names: set[str] = set()
        for row in table_rows:
            table_name = _required_row_text(row, "TableName")
            key = table_name.casefold()
            observed_table_names.add(key)
            tables.append(
                IRRBBSemanticModelTableMetadata(
                    name=table_name,
                    is_hidden=_optional_bool(_row_value(row, "IsHidden")),
                    columns=tuple(column_groups.get(key, ())),
                    measures=tuple(measure_groups.get(key, ())),
                )
            )

        unknown_column_tables = set(column_groups) - observed_table_names
        unknown_measure_tables = set(measure_groups) - observed_table_names
        if unknown_column_tables or unknown_measure_tables:
            raise ValueError("Power BI metadata references columns or measures from unknown tables")
        return tuple(tables)

    @staticmethod
    def _build_relationships(
        rows: list[dict[str, Any]],
    ) -> tuple[IRRBBSemanticModelRelationshipMetadata, ...]:
        return tuple(
            IRRBBSemanticModelRelationshipMetadata(
                name=_optional_text(_row_value(row, "RelationshipName")),
                from_table=_required_row_text(row, "FromTable"),
                from_column=_required_row_text(row, "FromColumn"),
                to_table=_required_row_text(row, "ToTable"),
                to_column=_required_row_text(row, "ToColumn"),
                is_active=_optional_bool(_row_value(row, "IsActive")),
                cross_filter_direction=_optional_text(_row_value(row, "CrossFilteringBehavior")),
                from_cardinality=_optional_text(_row_value(row, "FromCardinality")),
                to_cardinality=_optional_text(_row_value(row, "ToCardinality")),
            )
            for row in rows
        )


def _decode_arrow_rows(payload: bytes) -> list[dict[str, Any]]:
    if not payload:
        raise ValueError("Power BI metadata query returned an empty Arrow response")

    stream = io.BytesIO(payload)
    rows: list[dict[str, Any]] = []
    stream_count = 0
    while stream.tell() < len(payload):
        start_offset = stream.tell()
        try:
            reader = pa.ipc.open_stream(stream)
            table = reader.read_all()
        except (pa.ArrowInvalid, pa.ArrowIOError) as exc:
            raise ValueError("Power BI metadata query returned invalid Arrow content") from exc

        metadata = {
            key.decode("utf-8", errors="replace"): value.decode("utf-8", errors="replace")
            for key, value in (reader.schema.metadata or {}).items()
        }
        if metadata.get("IsError", "false").casefold() == "true":
            fault_code = metadata.get("FaultCode", "UNKNOWN")
            raise ConnectionError(f"Power BI metadata query failed with provider code {fault_code}")

        stream_count += 1
        rows.extend(table.to_pylist())
        if stream.tell() <= start_offset:
            raise ValueError("Power BI Arrow parser did not advance")

    if stream_count != 1:
        raise ValueError("Power BI metadata query returned an unexpected number of Arrow rowsets")
    return rows


def _require_power_bi_api_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != _POWER_BI_API_HOST:
        raise ValueError("Power BI HTTP transport rejected a non-Power-BI API URL")
    if not parsed.path.startswith("/v1.0/myorg/"):
        raise ValueError("Power BI HTTP transport rejected an unexpected API path")
    if parsed.username is not None or parsed.password is not None or parsed.port is not None:
        raise ValueError("Power BI HTTP transport rejected an unexpected API authority")


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == expected:
            return str(value)
    return None


def _row_value(row: Mapping[str, Any], expected_name: str) -> Any:
    expected = expected_name.casefold()
    for raw_name, value in row.items():
        normalized = str(raw_name).strip().strip("[]").casefold()
        if normalized == expected:
            return value
    return None


def _required_row_text(row: Mapping[str, Any], name: str) -> str:
    return _required_text(f"Power BI metadata field {name}", _row_value(row, name))


def _required_text(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Power BI optional metadata text must be a string")
    stripped = value.strip()
    return stripped or None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError("Power BI optional metadata boolean must be a boolean")
