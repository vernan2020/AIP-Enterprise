from __future__ import annotations

import json
from typing import Any

from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelColumnMetadata,
    IRRBBSemanticModelInspectionSnapshot,
    IRRBBSemanticModelMeasureMetadata,
    IRRBBSemanticModelRelationshipMetadata,
    IRRBBSemanticModelTableMetadata,
)
from aip.product.configured.irrbb.semantic_model_inspection_evidence import (
    SemanticModelInspectionEvidenceValidator,
)
from aip.product.configured.irrbb.semantic_model_inspection_report_contract import (
    SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
    SEMANTIC_MODEL_METADATA_REPORT_TYPE,
)


class SemanticModelInspectionEvidenceRenderer:
    """Render validated metadata snapshots into the governed transfer contract.

    The renderer is deliberately provider-neutral. It never accepts a raw Power BI
    response and never adds provider fields beyond the reviewed evidence contract.
    A rendered payload is revalidated before it leaves this boundary.
    """

    def __init__(
        self,
        *,
        validator: SemanticModelInspectionEvidenceValidator | None = None,
    ) -> None:
        if validator is None:
            validator = SemanticModelInspectionEvidenceValidator()
        self._validator = validator

    def render_payload(
        self,
        snapshot: IRRBBSemanticModelInspectionSnapshot,
    ) -> dict[str, Any]:
        """Render one snapshot and fail closed if it is not governed evidence."""

        payload: dict[str, Any] = {
            "report_type": SEMANTIC_MODEL_METADATA_REPORT_TYPE,
            "report_version": SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
            "source_id": snapshot.source_id,
            "logical_name": snapshot.logical_name,
            "provider_workspace_reference": snapshot.provider_workspace_reference,
            "provider_model_reference": snapshot.provider_model_reference,
            "provider_model_name": snapshot.provider_model_name,
            "inspection_method": snapshot.inspection_method,
            "observed_at": snapshot.observed_at.isoformat(),
            "schema_freshness": snapshot.schema_freshness.value,
            "row_data_included": snapshot.row_data_included,
            "expressions_included": snapshot.expressions_included,
            "tables": [self._render_table(table) for table in snapshot.tables],
            "relationships": [
                self._render_relationship(relationship)
                for relationship in snapshot.relationships
            ],
        }
        self._validator.validate_report(payload)
        return payload

    def render_json_document(
        self,
        snapshot: IRRBBSemanticModelInspectionSnapshot,
    ) -> str:
        """Render deterministic UTF-8-safe JSON for review or evidence transfer."""

        return json.dumps(
            self.render_payload(snapshot),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _render_table(table: IRRBBSemanticModelTableMetadata) -> dict[str, Any]:
        return {
            "name": table.name,
            "is_hidden": table.is_hidden,
            "columns": [
                SemanticModelInspectionEvidenceRenderer._render_column(column)
                for column in table.columns
            ],
            "measures": [
                SemanticModelInspectionEvidenceRenderer._render_measure(measure)
                for measure in table.measures
            ],
        }

    @staticmethod
    def _render_column(column: IRRBBSemanticModelColumnMetadata) -> dict[str, Any]:
        return {
            "name": column.name,
            "data_type": column.data_type,
            "is_hidden": column.is_hidden,
        }

    @staticmethod
    def _render_measure(measure: IRRBBSemanticModelMeasureMetadata) -> dict[str, Any]:
        return {
            "name": measure.name,
            "is_hidden": measure.is_hidden,
        }

    @staticmethod
    def _render_relationship(
        relationship: IRRBBSemanticModelRelationshipMetadata,
    ) -> dict[str, Any]:
        return {
            "name": relationship.name,
            "from_table": relationship.from_table,
            "from_column": relationship.from_column,
            "to_table": relationship.to_table,
            "to_column": relationship.to_column,
            "is_active": relationship.is_active,
            "cross_filter_direction": relationship.cross_filter_direction,
            "from_cardinality": relationship.from_cardinality,
            "to_cardinality": relationship.to_cardinality,
        }
