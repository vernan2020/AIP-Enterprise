from __future__ import annotations

import io
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa
import pytest

from aip.application.irrbb.semantic_model_inspection import IRRBBSemanticModelSchemaFreshness
from aip.product.configured.irrbb.physical_source_registry import CREDIT_SEMANTIC_MODEL_SOURCE
from aip.product.configured.irrbb.power_bi_semantic_metadata_fetcher import (
    ConfiguredPowerBISemanticMetadataSnapshotFetcher,
    PowerBIHTTPResponse,
    UrllibPowerBIHTTPTransport,
)
from aip.product.configured.irrbb.power_bi_semantic_route import PowerBISemanticModelRoute

_WORKSPACE_ID = "12345678-1234-4234-8234-1234567890ab"
_DATASET_ID = "22345678-1234-4234-8234-1234567890ab"
_AUTH_PROFILE = "security.auth.power_bi.readonly"
_OBSERVED_AT = datetime(2026, 9, 17, 18, 0, tzinfo=timezone.utc)


class _TokenProvider:
    def __init__(self, token: str = "unit-token") -> None:
        self.token = token
        self.requested_profiles: list[str] = []

    def require_access_token(self, *, authentication_profile_key: str) -> str:
        self.requested_profiles.append(authentication_profile_key)
        return self.token


class _FakeHTTPTransport:
    def __init__(
        self,
        *,
        dataset_id: str = _DATASET_ID,
        dataset_name: str = "Credito",
        arrow_error_for: str | None = None,
        status_code: int = 200,
    ) -> None:
        self.dataset_id = dataset_id
        self.dataset_name = dataset_name
        self.arrow_error_for = arrow_error_for
        self.status_code = status_code
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> PowerBIHTTPResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.status_code != 200:
            return PowerBIHTTPResponse(
                status_code=self.status_code,
                headers={"Content-Type": "application/json"},
                body=b"{}",
            )
        if method == "GET":
            return PowerBIHTTPResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"id": self.dataset_id, "name": self.dataset_name}).encode(),
            )

        assert body is not None
        request_payload = json.loads(body.decode("utf-8"))
        query = request_payload["query"]
        result_name, rows = _rows_for_query(query)
        if self.arrow_error_for == result_name:
            arrow_body = _arrow_bytes(
                [
                    {
                        "ErrorCode": "ProviderError",
                        "ErrorMessage": "suppressed by adapter",
                    }
                ],
                schema_metadata={b"IsError": b"true", b"FaultCode": b"0xC0000001"},
            )
        else:
            arrow_body = _arrow_bytes(rows)
        return PowerBIHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/vnd.apache.arrow.stream"},
            body=arrow_body,
        )


def _route(*, workspace_id: str | None = _WORKSPACE_ID) -> PowerBISemanticModelRoute:
    return PowerBISemanticModelRoute.from_strings(
        configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        workspace_id=workspace_id,
        dataset_id=_DATASET_ID,
        authentication_profile_key=_AUTH_PROFILE,
    )


def _arrow_bytes(
    rows: list[dict[str, Any]],
    *,
    schema_metadata: dict[bytes, bytes] | None = None,
) -> bytes:
    if rows:
        table = pa.Table.from_pylist(rows)
    else:
        table = pa.table({"Empty": pa.array([], type=pa.string())})
    if schema_metadata:
        table = table.replace_schema_metadata(schema_metadata)
    sink = io.BytesIO()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue()


def _rows_for_query(query: str) -> tuple[str, list[dict[str, Any]]]:
    if "INFO.VIEW.TABLES()" in query:
        return (
            "tables",
            [
                {"TableName": "Accounts", "IsHidden": False},
                {"TableName": "Products", "IsHidden": False},
            ],
        )
    if "INFO.VIEW.COLUMNS()" in query:
        return (
            "columns",
            [
                {
                    "TableName": "Accounts",
                    "ColumnName": "Balance",
                    "DataType": "Decimal",
                    "IsHidden": False,
                },
                {
                    "TableName": "Accounts",
                    "ColumnName": "ProductId",
                    "DataType": "Int64",
                    "IsHidden": True,
                },
                {
                    "TableName": "Products",
                    "ColumnName": "ProductId",
                    "DataType": "Int64",
                    "IsHidden": False,
                },
            ],
        )
    if "INFO.VIEW.MEASURES()" in query:
        return (
            "measures",
            [
                {
                    "TableName": "Accounts",
                    "MeasureName": "Total Balance",
                    "IsHidden": False,
                }
            ],
        )
    if "INFO.VIEW.RELATIONSHIPS()" in query:
        return (
            "relationships",
            [
                {
                    "RelationshipName": "accounts-products",
                    "FromTable": "Accounts",
                    "FromColumn": "ProductId",
                    "ToTable": "Products",
                    "ToColumn": "ProductId",
                    "IsActive": True,
                    "CrossFilteringBehavior": "OneDirection",
                    "FromCardinality": "Many",
                    "ToCardinality": "One",
                }
            ],
        )
    raise AssertionError(f"unexpected DAX query: {query}")


def _fetcher(
    *,
    token_provider: _TokenProvider | None = None,
    http_transport: _FakeHTTPTransport | None = None,
) -> ConfiguredPowerBISemanticMetadataSnapshotFetcher:
    return ConfiguredPowerBISemanticMetadataSnapshotFetcher(
        token_provider=token_provider or _TokenProvider(),
        http_transport=http_transport or _FakeHTTPTransport(),
        timeout_seconds=12.5,
        now_provider=lambda: _OBSERVED_AT,
    )


def test_fetcher_reads_only_projected_metadata_and_builds_source_neutral_snapshot() -> None:
    token_provider = _TokenProvider()
    http_transport = _FakeHTTPTransport()
    snapshot = _fetcher(
        token_provider=token_provider,
        http_transport=http_transport,
    ).fetch_metadata(
        source=CREDIT_SEMANTIC_MODEL_SOURCE,
        route=_route(),
    )

    assert token_provider.requested_profiles == [_AUTH_PROFILE]
    assert snapshot.source_id == CREDIT_SEMANTIC_MODEL_SOURCE.source_id
    assert snapshot.logical_name == "Credito"
    assert snapshot.provider_workspace_reference == _WORKSPACE_ID
    assert snapshot.provider_model_reference == _DATASET_ID
    assert snapshot.provider_model_name == "Credito"
    assert snapshot.observed_at == _OBSERVED_AT
    assert snapshot.schema_freshness is IRRBBSemanticModelSchemaFreshness.UNKNOWN
    assert snapshot.row_data_included is False
    assert snapshot.expressions_included is False
    assert [table.name for table in snapshot.tables] == ["Accounts", "Products"]
    assert [column.name for column in snapshot.tables[0].columns] == ["Balance", "ProductId"]
    assert [measure.name for measure in snapshot.tables[0].measures] == ["Total Balance"]
    assert len(snapshot.relationships) == 1
    assert snapshot.relationships[0].from_table == "Accounts"
    assert snapshot.relationships[0].to_table == "Products"

    assert len(http_transport.calls) == 5
    assert http_transport.calls[0]["method"] == "GET"
    assert http_transport.calls[0]["url"].endswith(f"/datasets/{_DATASET_ID}")
    for call in http_transport.calls[1:]:
        assert call["method"] == "POST"
        assert call["url"].endswith(f"/datasets/{_DATASET_ID}/executeDaxQueries")
        request_body = json.loads(call["body"].decode("utf-8"))
        assert "INFO.VIEW." in request_body["query"]
        assert "Expression" not in request_body["query"]
        assert request_body["schemaOnly"] is False
        assert call["headers"]["Accept"] == "application/vnd.apache.arrow.stream"


def test_fetcher_supports_my_workspace_without_inventing_workspace_uuid() -> None:
    snapshot = _fetcher().fetch_metadata(
        source=CREDIT_SEMANTIC_MODEL_SOURCE,
        route=_route(workspace_id=None),
    )

    assert snapshot.provider_workspace_reference == "MY_WORKSPACE"


def test_dataset_identity_mismatch_fails_before_any_dax_metadata_query() -> None:
    transport = _FakeHTTPTransport(dataset_id="32345678-1234-4234-8234-1234567890ab")

    with pytest.raises(ValueError, match="dataset identity does not match"):
        _fetcher(http_transport=transport).fetch_metadata(
            source=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=_route(),
        )

    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "GET"


def test_provider_arrow_error_rowset_fails_closed_even_with_http_200() -> None:
    transport = _FakeHTTPTransport(arrow_error_for="columns")

    with pytest.raises(ConnectionError, match="provider code 0xC0000001"):
        _fetcher(http_transport=transport).fetch_metadata(
            source=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=_route(),
        )


def test_blank_access_token_fails_before_provider_io() -> None:
    transport = _FakeHTTPTransport()

    with pytest.raises(ValueError, match="returned no access token"):
        _fetcher(
            token_provider=_TokenProvider(token=""),
            http_transport=transport,
        ).fetch_metadata(
            source=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=_route(),
        )

    assert transport.calls == []


def test_non_success_http_status_is_not_interpreted_as_metadata() -> None:
    transport = _FakeHTTPTransport(status_code=403)

    with pytest.raises(ConnectionError, match="HTTP 403"):
        _fetcher(http_transport=transport).fetch_metadata(
            source=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=_route(),
        )


def test_production_transport_rejects_non_power_bi_urls_before_network_io() -> None:
    transport = UrllibPowerBIHTTPTransport()

    with pytest.raises(ValueError, match="non-Power-BI API URL"):
        transport.request(
            method="GET",
            url="https://example.invalid/v1.0/myorg/datasets/anything",
            headers={},
            body=None,
            timeout_seconds=1.0,
        )
