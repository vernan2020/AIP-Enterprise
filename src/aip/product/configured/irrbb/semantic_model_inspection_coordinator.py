from __future__ import annotations

from dataclasses import dataclass

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceRegistry,
    IRRBBPhysicalSourceSegment,
)
from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelInspectionSnapshot,
    IRRBBSemanticModelMetadataInspector,
)
from aip.product.configured.irrbb.physical_source_registry import (
    institutional_irrbb_physical_source_registry,
)
from aip.product.configured.irrbb.semantic_model_inspection_renderer import (
    SemanticModelInspectionEvidenceRenderer,
)


@dataclass(frozen=True, slots=True)
class GovernedSemanticModelInspectionResult:
    """One metadata-only inspection run bound to the requested governed source."""

    source: IRRBBPhysicalSourceDescriptor
    snapshot: IRRBBSemanticModelInspectionSnapshot
    evidence_document: str


class GovernedSemanticModelInspectionCoordinator:
    """Orchestrate semantic-model discovery without provider-specific behavior.

    The coordinator resolves the governed source by segment, invokes the injected
    application inspector port and rejects source substitution before rendering the
    transferable evidence contract.
    """

    def __init__(
        self,
        *,
        inspector: IRRBBSemanticModelMetadataInspector,
        renderer: SemanticModelInspectionEvidenceRenderer | None = None,
        registry: IRRBBPhysicalSourceRegistry | None = None,
    ) -> None:
        self._inspector = inspector
        self._renderer = (
            renderer
            if renderer is not None
            else SemanticModelInspectionEvidenceRenderer()
        )
        self._registry = (
            registry
            if registry is not None
            else institutional_irrbb_physical_source_registry()
        )

    def inspect(
        self,
        *,
        segment: IRRBBPhysicalSourceSegment,
    ) -> GovernedSemanticModelInspectionResult:
        """Inspect one governed semantic-model segment and render safe evidence."""

        source = self._registry.require(segment)
        if source.kind is not IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL:
            raise ValueError(
                f"physical source for segment {segment.value} is not a semantic model"
            )

        snapshot = self._inspector.inspect(source=source)
        self._require_requested_source(source=source, snapshot=snapshot)
        evidence_document = self._renderer.render_json_document(snapshot)
        return GovernedSemanticModelInspectionResult(
            source=source,
            snapshot=snapshot,
            evidence_document=evidence_document,
        )

    @staticmethod
    def _require_requested_source(
        *,
        source: IRRBBPhysicalSourceDescriptor,
        snapshot: IRRBBSemanticModelInspectionSnapshot,
    ) -> None:
        if snapshot.source_id != source.source_id:
            raise ValueError(
                "semantic-model inspector returned evidence for a different source_id"
            )
        if snapshot.logical_name != source.logical_name:
            raise ValueError(
                "semantic-model inspector returned evidence for a different logical_name"
            )
