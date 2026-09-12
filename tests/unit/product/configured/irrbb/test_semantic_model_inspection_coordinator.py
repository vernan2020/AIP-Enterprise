from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceSegment,
)
from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelColumnMetadata,
    IRRBBSemanticModelInspectionSnapshot,
    IRRBBSemanticModelSchemaFreshness,
    IRRBBSemanticModelTableMetadata,
)
from aip.product.configured.irrbb.physical_source_registry import (
    CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.semantic_model_inspection_coordinator import (
    GovernedSemanticModelInspectionCoordinator,
)
from aip.product.configured.irrbb.semantic_model_inspection_evidence import (
    SemanticModelInspectionEvidenceValidator,
)


class _RecordingInspector:
    def __init__(self, snapshot: IRRBBSemanticModelInspectionSnapshot) -> None:
        self._snapshot = snapshot
        self.calls: list[IRRBBPhysicalSourceDescriptor] = []

    def inspect(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
    ) -> IRRBBSemanticModelInspectionSnapshot:
        self.calls.append(source)
        return self._snapshot


def _snapshot(
    *,
    source: IRRBBPhysicalSourceDescriptor = CREDIT_SEMANTIC_MODEL_SOURCE,
    logical_name: str | None = None,
) -> IRRBBSemanticModelInspectionSnapshot:
    table = IRRBBSemanticModelTableMetadata(
        name="Operations",
        is_hidden=False,
        columns=(
            IRRBBSemanticModelColumnMetadata(
                name="OperationId",
                data_type="String",
                is_hidden=False,
            ),
        ),
        measures=(),
    )
    model_name = source.logical_name if logical_name is None else logical_name
    return IRRBBSemanticModelInspectionSnapshot(
        source_id=source.source_id,
        logical_name=model_name,
        provider_workspace_reference="workspace-runtime-reference",
        provider_model_reference="model-runtime-reference",
        provider_model_name=model_name,
        inspection_method="provider-metadata-scan",
        observed_at=datetime(2026, 9, 10, 23, 10, tzinfo=UTC),
        schema_freshness=IRRBBSemanticModelSchemaFreshness.CURRENT,
        row_data_included=False,
        expressions_included=False,
        tables=(table,),
        relationships=(),
    )


@pytest.mark.parametrize(
    ("segment", "source"),
    [
        (IRRBBPhysicalSourceSegment.CREDIT, CREDIT_SEMANTIC_MODEL_SOURCE),
        (
            IRRBBPhysicalSourceSegment.TERM_DEPOSIT,
            TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
        ),
    ],
)
def test_coordinator_inspects_requested_governed_semantic_model(
    segment: IRRBBPhysicalSourceSegment,
    source: IRRBBPhysicalSourceDescriptor,
) -> None:
    snapshot = _snapshot(source=source)
    inspector = _RecordingInspector(snapshot)
    coordinator = GovernedSemanticModelInspectionCoordinator(inspector=inspector)

    result = coordinator.inspect(segment=segment)
    parsed = SemanticModelInspectionEvidenceValidator().parse_json_document(
        result.evidence_document
    )

    assert inspector.calls == [source]
    assert result.source is source
    assert result.snapshot == snapshot
    assert parsed.snapshot == snapshot


def test_coordinator_rejects_non_semantic_registered_segment_before_inspection() -> None:
    inspector = _RecordingInspector(_snapshot())
    coordinator = GovernedSemanticModelInspectionCoordinator(inspector=inspector)

    with pytest.raises(ValueError, match="is not a semantic model"):
        coordinator.inspect(segment=IRRBBPhysicalSourceSegment.BORROWING)

    assert inspector.calls == []


def test_coordinator_rejects_governed_source_substitution() -> None:
    inspector = _RecordingInspector(_snapshot(source=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE))
    coordinator = GovernedSemanticModelInspectionCoordinator(inspector=inspector)

    with pytest.raises(ValueError, match="different source_id"):
        coordinator.inspect(segment=IRRBBPhysicalSourceSegment.CREDIT)

    assert inspector.calls == [CREDIT_SEMANTIC_MODEL_SOURCE]


def test_coordinator_rejects_logical_name_substitution() -> None:
    inspector = _RecordingInspector(_snapshot(logical_name="OtherCreditModel"))
    coordinator = GovernedSemanticModelInspectionCoordinator(inspector=inspector)

    with pytest.raises(ValueError, match="different logical_name"):
        coordinator.inspect(segment=IRRBBPhysicalSourceSegment.CREDIT)

    assert inspector.calls == [CREDIT_SEMANTIC_MODEL_SOURCE]
