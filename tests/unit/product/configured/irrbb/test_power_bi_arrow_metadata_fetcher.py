from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pyarrow as pa
import pytest

from aip.product.configured.irrbb.physical_source_registry import CREDIT_SEMANTIC_MODEL_SOURCE
from aip.product.configured.irrbb.power_bi_arrow_metadata_fetcher import (
    PowerBIArrowSemanticMetadataSnapshotFetcher,
)
from aip.product.configured.irrbb.power_bi_semantic_route import PowerBISemanticModelRoute

_WORKSPACE_ID = "12345678-1234-4234-8234-1234567890ab"
_DATASET_ID = "22345678-1234-4234-8234-1234567890ab"


class _TokenProvider:
    def __init__(self, token: str = "opaque-token") -> None:
        self.token = token
        self.profile_keys: list[str] = []

    def require_access_token(self, *, authentication_profile_key: str) -> str:
        self.profile_keys.append(authentication_profile_key)
        return self.token


class _Transport:
    def __init__(self, *, dataset_name: str = "Credito") -> None:
        self.dataset_name = dataset_name
        self.get_calls: list[tuple[str, str]] = []
        self.post_calls: list[tuple[str, str, dict[str, Any]]] = []

    def get_json(self, *, url: str, access_token: str) -> dict[str, Any]:
        self.get_calls.append((url, access_token))
        return {"id": _DATASET_ID, "name": self.dataset_name}

    def post_arrow(
        self,
        *,
        url: str,
        access_token: str,
        payload: dict[str, Any],
    ) -> bytes:
        self.post_calls.append((url, access_token, dict(payload)))
        query = str(payload["query"])
        if "INFO.VIEW.TABLES()" in query:
            return _arrow_bytes(
                [
                    {"Name": "Operations", "IsHidden": False},
                    {"Name": "Counterparty", "IsHidden": True},
                ]
            )
        if "INFO.VIEW.COLUMNS()" in query:
            return _arrow_bytes(
                [
                    {
                        "Table": "Operations",
                        "Name": "OperationId",
                        "DataType": "String",
                        "IsHidden": False,
                    },
                    {
                        "Table": "Operations",
                        "Name": "CounterpartyId",
                        "DataType": "Int64",
                        "IsHidden": False,
                    },
                    {
                        "Table": "Counterparty",
                        "Name": "CounterpartyId",
                        "DataType": "Int64",
                        "IsHidden": False,
                    },
                ]
            )
        if "INFO.VIEW.MEASURES()" in query:
            return _arrow_bytes(
                [{"Table": "Operations", "Name": "ExposureCount", "IsHidden": True}]
            )
        if "INFO.VIEW.RELATIONSHIPS()" in query:
            return _arrow_bytes(
                [
                    {
                        "Name": "relationship-guid",
                        "FromTable": "Operations",
                        "FromColumn": "CounterpartyId",
                        "ToTable": "Counterparty",
                        "ToColumn": "CounterpartyId",
                        "IsActive": True,
                        "CrossFilteringBehavior": "OneDirection",
                        "FromCardinality": "Many",
                        "ToCardinality": "One",
                    }
                ]
            )
        raise AssertionError(f"unexpected metadata query: {query}")


def _arrow_bytes(rows: list[dict[str, Any]]) -> bytes:
    table = pa.Table.from_pylist(rows)
    sink = io.BytesIO()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue()


def _route(*, workspace_id: str | None = _WORKSPACE_ID) -> PowerBISemanticModelRoute:
    return PowerBISemanticModelRoute(
        configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        workspace_id=None if workspace_id is None else UUID(workspace_id),
        dataset_id=UUID(_DATASET_ID),
        authentication_profile_key="security.auth.power_bi.readonly",
    )


def test_fetcher_builds_metadata_only_snapshot_from_governed_power_bi_route() -> None:
    token_provider = _TokenProvider()
    transport = _Transport()
    observed_at = datetime(2026, 9, 18, 8, 30, tzinfo=UTC)
    fetcher = PowerBIArrowSemanticMetadataSnapshotFetcher(
        access_token_provider=token_provider,
        transport=transport,
        clock=lambda: observed_at,
    )

    snapshot = fetcher.fetch_metadata(
        source=CREDIT_SEMANTIC_MODEL_SOURCE,
        route=_route(),
    )

    assert token_provider.profile_keys == ["security.auth.power_bi.readonly"]
    assert transport.get_calls == [
        (
            (
                "https://api.powerbi.com/v1.0/myorg/groups/"
                f"{_WORKSPACE_ID}/datasets/{_DATASET_ID}"
            ),
            "opaque-token",
        )
    ]
    assert len(transport.post_calls) == 4
    assert all(call[1] == "opaque-token" for call in transport.post_calls)
    assert all("Expression" not in str(call[2]["query"]) for call in transport.post_calls)

    assert snapshot.source_id == CREDIT_SEMANTIC_MODEL_SOURCE.source_id
    assert snapshot.logical_name == "Credito"
    assert snapshot.provider_model_name == "Credito"
    assert snapshot.provider_model_reference == f"powerbi://dataset/{_DATASET_ID}"
    assert snapshot.provider_workspace_reference == f"powerbi://workspace/{_WORKSPACE_ID}"
    assert snapshot.observed_at == observed_at
    assert snapshot.row_data_included is False
    assert snapshot.expressions_included is False
    assert tuple(table.name for table in snapshot.tables) == ("Operations", "Counterparty")
    assert tuple(column.name for column in snapshot.tables[0].columns) == (
        "OperationId",
        "CounterpartyId",
    )
    assert tuple(measure.name for measure in snapshot.tables[0].measures) == ("ExposureCount",)
    assert snapshot.relationships[0].from_table == "Operations"
    assert snapshot.relationships[0].to_table == "Counterparty"


def test_fetcher_rejects_provider_model_name_mismatch_before_schema_queries() -> None:
    transport = _Transport(dataset_name="UnexpectedModel")
    fetcher = PowerBIArrowSemanticMetadataSnapshotFetcher(
        access_token_provider=_TokenProvider(),
        transport=transport,
    )

    with pytest.raises(ValueError, match="dataset name.*governed physical source"):
        fetcher.fetch_metadata(
            source=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=_route(),
        )

    assert transport.post_calls == []


def test_fetcher_uses_non_secret_my_workspace_reference_for_dataset_only_route() -> None:
    fetcher = PowerBIArrowSemanticMetadataSnapshotFetcher(
        access_token_provider=_TokenProvider(),
        transport=_Transport(),
    )

    snapshot = fetcher.fetch_metadata(
        source=CREDIT_SEMANTIC_MODEL_SOURCE,
        route=_route(workspace_id=None),
    )

    assert snapshot.provider_workspace_reference == "powerbi://my-workspace"


def test_fetcher_rejects_invalid_token_without_provider_io() -> None:
    transport = _Transport()
    fetcher = PowerBIArrowSemanticMetadataSnapshotFetcher(
        access_token_provider=_TokenProvider(token=" secret "),
        transport=transport,
    )

    with pytest.raises(ValueError, match="invalid token"):
        fetcher.fetch_metadata(
            source=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=_route(),
        )

    assert transport.get_calls == []
    assert transport.post_calls == []
