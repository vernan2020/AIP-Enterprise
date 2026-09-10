from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelColumnMetadata,
    IRRBBSemanticModelInspectionSnapshot,
    IRRBBSemanticModelMeasureMetadata,
    IRRBBSemanticModelRelationshipMetadata,
    IRRBBSemanticModelSchemaFreshness,
    IRRBBSemanticModelTableMetadata,
)


def _column(name: str, data_type: str = "String") -> IRRBBSemanticModelColumnMetadata:
    return IRRBBSemanticModelColumnMetadata(
        name=name,
        data_type=data_type,
        is_hidden=False,
    )


def _table(
    name: str,
    *column_names: str,
) -> IRRBBSemanticModelTableMetadata:
    return IRRBBSemanticModelTableMetadata(
        name=name,
        is_hidden=False,
        columns=tuple(_column(column_name) for column_name in column_names),
        measures=(),
    )


def _snapshot(
    *,
    row_data_included: bool = False,
    expressions_included: bool = False,
    tables: tuple[IRRBBSemanticModelTableMetadata, ...] | None = None,
    relationships: tuple[IRRBBSemanticModelRelationshipMetadata, ...] = (),
    observed_at: datetime | None = None,
) -> IRRBBSemanticModelInspectionSnapshot:
    return IRRBBSemanticModelInspectionSnapshot(
        source_id="coopealianza.credit.powerbi.credito",
        logical_name="Credito",
        provider_workspace_reference="workspace-runtime-reference",
        provider_model_reference="model-runtime-reference",
        provider_model_name="Credito",
        inspection_method="provider-metadata-scan",
        observed_at=observed_at or datetime(2026, 9, 10, 22, 30, tzinfo=UTC),
        schema_freshness=IRRBBSemanticModelSchemaFreshness.CURRENT,
        row_data_included=row_data_included,
        expressions_included=expressions_included,
        tables=tables or (_table("Credito", "Operacion", "Saldo"),),
        relationships=relationships,
    )


def test_metadata_snapshot_accepts_auditable_schema_without_rows_or_expressions() -> None:
    measure = IRRBBSemanticModelMeasureMetadata(name="Conteo", is_hidden=False)
    table = IRRBBSemanticModelTableMetadata(
        name="Credito",
        is_hidden=False,
        columns=(_column("Operacion"), _column("Saldo", "Decimal")),
        measures=(measure,),
    )

    snapshot = _snapshot(tables=(table,))

    assert snapshot.provider_model_name == "Credito"
    assert snapshot.row_data_included is False
    assert snapshot.expressions_included is False
    assert snapshot.tables[0].columns[1].data_type == "Decimal"


@pytest.mark.parametrize(
    ("row_data_included", "expressions_included", "message"),
    [
        (True, False, "must not contain row data"),
        (False, True, "must not contain expressions"),
    ],
)
def test_metadata_snapshot_rejects_content_outside_metadata_boundary(
    row_data_included: bool,
    expressions_included: bool,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _snapshot(
            row_data_included=row_data_included,
            expressions_included=expressions_included,
        )


def test_metadata_snapshot_requires_timezone_aware_observation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _snapshot(observed_at=datetime(2026, 9, 10, 22, 30))


def test_table_rejects_case_insensitive_duplicate_columns() -> None:
    with pytest.raises(ValueError, match="columns must be unique"):
        IRRBBSemanticModelTableMetadata(
            name="Credito",
            is_hidden=False,
            columns=(_column("Operacion"), _column("operacion")),
            measures=(),
        )


def test_snapshot_rejects_case_insensitive_duplicate_tables() -> None:
    with pytest.raises(ValueError, match="tables must be unique"):
        _snapshot(
            tables=(
                _table("Credito", "Operacion"),
                _table("credito", "Saldo"),
            )
        )


def test_snapshot_accepts_relationships_that_resolve_to_observed_schema() -> None:
    relationship = IRRBBSemanticModelRelationshipMetadata(
        name="CreditoCliente",
        from_table="Credito",
        from_column="ClienteId",
        to_table="Cliente",
        to_column="ClienteId",
        is_active=True,
        cross_filter_direction="Single",
        from_cardinality="Many",
        to_cardinality="One",
    )

    snapshot = _snapshot(
        tables=(
            _table("Credito", "Operacion", "ClienteId"),
            _table("Cliente", "ClienteId"),
        ),
        relationships=(relationship,),
    )

    assert snapshot.relationships == (relationship,)


def test_snapshot_rejects_relationships_to_unobserved_columns() -> None:
    relationship = IRRBBSemanticModelRelationshipMetadata(
        name=None,
        from_table="Credito",
        from_column="ClienteId",
        to_table="Cliente",
        to_column="NoExiste",
        is_active=None,
        cross_filter_direction=None,
        from_cardinality=None,
        to_cardinality=None,
    )

    with pytest.raises(ValueError, match="unknown to-column"):
        _snapshot(
            tables=(
                _table("Credito", "ClienteId"),
                _table("Cliente", "ClienteId"),
            ),
            relationships=(relationship,),
        )


def test_snapshot_rejects_duplicate_relationship_endpoints() -> None:
    first = IRRBBSemanticModelRelationshipMetadata(
        name="R1",
        from_table="Credito",
        from_column="ClienteId",
        to_table="Cliente",
        to_column="ClienteId",
        is_active=True,
        cross_filter_direction=None,
        from_cardinality=None,
        to_cardinality=None,
    )
    duplicate = IRRBBSemanticModelRelationshipMetadata(
        name="R2",
        from_table="credito",
        from_column="clienteid",
        to_table="cliente",
        to_column="clienteid",
        is_active=False,
        cross_filter_direction=None,
        from_cardinality=None,
        to_cardinality=None,
    )

    with pytest.raises(ValueError, match="duplicate relationships"):
        _snapshot(
            tables=(
                _table("Credito", "ClienteId"),
                _table("Cliente", "ClienteId"),
            ),
            relationships=(first, duplicate),
        )
