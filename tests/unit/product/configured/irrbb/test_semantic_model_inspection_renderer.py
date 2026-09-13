from __future__ import annotations

import json
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
from aip.product.configured.irrbb.physical_source_registry import (
    CREDIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.semantic_model_inspection_evidence import (
    SemanticModelInspectionEvidenceValidator,
)
from aip.product.configured.irrbb.semantic_model_inspection_renderer import (
    SemanticModelInspectionEvidenceRenderer,
)
from aip.product.configured.irrbb.semantic_model_inspection_report_contract import (
    SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
    SEMANTIC_MODEL_METADATA_REPORT_TYPE,
)


def _snapshot(
    *,
    source_id: str = CREDIT_SEMANTIC_MODEL_SOURCE.source_id,
    logical_name: str = CREDIT_SEMANTIC_MODEL_SOURCE.logical_name,
    provider_model_name: str = CREDIT_SEMANTIC_MODEL_SOURCE.logical_name,
) -> IRRBBSemanticModelInspectionSnapshot:
    operations = IRRBBSemanticModelTableMetadata(
        name="Operations",
        is_hidden=False,
        columns=(
            IRRBBSemanticModelColumnMetadata(
                name="OperationId",
                data_type="String",
                is_hidden=False,
            ),
            IRRBBSemanticModelColumnMetadata(
                name="CustomerId",
                data_type="String",
                is_hidden=False,
            ),
        ),
        measures=(
            IRRBBSemanticModelMeasureMetadata(
                name="OperationCount",
                is_hidden=False,
            ),
        ),
    )
    customers = IRRBBSemanticModelTableMetadata(
        name="Customers",
        is_hidden=False,
        columns=(
            IRRBBSemanticModelColumnMetadata(
                name="CustomerId",
                data_type="String",
                is_hidden=False,
            ),
        ),
        measures=(),
    )
    relationship = IRRBBSemanticModelRelationshipMetadata(
        name="OperationsCustomers",
        from_table="Operations",
        from_column="CustomerId",
        to_table="Customers",
        to_column="CustomerId",
        is_active=True,
        cross_filter_direction="Single",
        from_cardinality="Many",
        to_cardinality="One",
    )
    return IRRBBSemanticModelInspectionSnapshot(
        source_id=source_id,
        logical_name=logical_name,
        provider_workspace_reference="workspace-runtime-reference",
        provider_model_reference="model-runtime-reference",
        provider_model_name=provider_model_name,
        inspection_method="provider-metadata-scan",
        observed_at=datetime(2026, 9, 10, 23, 0, tzinfo=UTC),
        schema_freshness=IRRBBSemanticModelSchemaFreshness.CURRENT,
        row_data_included=False,
        expressions_included=False,
        tables=(operations, customers),
        relationships=(relationship,),
    )


def test_renderer_round_trips_through_strict_evidence_validator() -> None:
    snapshot = _snapshot()
    renderer = SemanticModelInspectionEvidenceRenderer()

    document = renderer.render_json_document(snapshot)
    bundle = SemanticModelInspectionEvidenceValidator().parse_json_document(document)

    assert bundle.source is CREDIT_SEMANTIC_MODEL_SOURCE
    assert bundle.snapshot == snapshot


def test_renderer_emits_only_reviewed_transfer_contract() -> None:
    payload = SemanticModelInspectionEvidenceRenderer().render_payload(_snapshot())

    assert payload["report_type"] == SEMANTIC_MODEL_METADATA_REPORT_TYPE
    assert payload["report_version"] == SEMANTIC_MODEL_INSPECTION_REPORT_VERSION
    assert payload["row_data_included"] is False
    assert payload["expressions_included"] is False

    encoded = json.dumps(payload)
    assert '"rows"' not in encoded
    assert '"expression"' not in encoded
    assert '"source"' not in encoded


def test_renderer_json_is_deterministic_for_same_snapshot() -> None:
    renderer = SemanticModelInspectionEvidenceRenderer()
    snapshot = _snapshot()

    first = renderer.render_json_document(snapshot)
    second = renderer.render_json_document(snapshot)

    assert first == second


def test_renderer_rejects_snapshot_not_bound_to_governed_source() -> None:
    renderer = SemanticModelInspectionEvidenceRenderer()
    snapshot = _snapshot(
        source_id="unregistered.semantic.model",
        logical_name="UnknownModel",
        provider_model_name="UnknownModel",
    )

    with pytest.raises(ValueError, match="not a governed Power BI RTILB source"):
        renderer.render_payload(snapshot)


def test_renderer_rejects_governed_source_name_mismatch() -> None:
    renderer = SemanticModelInspectionEvidenceRenderer()
    snapshot = _snapshot(
        logical_name="OtherModel",
        provider_model_name="OtherModel",
    )

    with pytest.raises(ValueError, match="logical_name does not match"):
        renderer.render_payload(snapshot)
