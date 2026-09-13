from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceDescriptor
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
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.semantic_model_inspection_report_contract import (
    SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
    SEMANTIC_MODEL_METADATA_REPORT_TYPE,
)

_REPORT_KEYS = frozenset(
    {
        "report_type",
        "report_version",
        "source_id",
        "logical_name",
        "provider_workspace_reference",
        "provider_model_reference",
        "provider_model_name",
        "inspection_method",
        "observed_at",
        "schema_freshness",
        "row_data_included",
        "expressions_included",
        "tables",
        "relationships",
    }
)
_TABLE_KEYS = frozenset({"name", "is_hidden", "columns", "measures"})
_COLUMN_KEYS = frozenset({"name", "data_type", "is_hidden"})
_MEASURE_KEYS = frozenset({"name", "is_hidden"})
_RELATIONSHIP_KEYS = frozenset(
    {
        "name",
        "from_table",
        "from_column",
        "to_table",
        "to_column",
        "is_active",
        "cross_filter_direction",
        "from_cardinality",
        "to_cardinality",
    }
)
_GOVERNED_SEMANTIC_MODEL_SOURCES = {
    CREDIT_SEMANTIC_MODEL_SOURCE.source_id: CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.source_id: TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
}


@dataclass(frozen=True, slots=True)
class SemanticModelInspectionEvidenceBundle:
    """Validated metadata evidence bound to one governed semantic-model source."""

    source: IRRBBPhysicalSourceDescriptor
    snapshot: IRRBBSemanticModelInspectionSnapshot


class SemanticModelInspectionEvidenceValidator:
    """Validate transferred metadata-only evidence without assigning RTILB meaning."""

    def parse_json_document(self, document: str) -> SemanticModelInspectionEvidenceBundle:
        """Parse and validate one complete semantic-model inspection JSON report."""

        try:
            payload = json.loads(document)
        except json.JSONDecodeError as exc:
            raise ValueError("semantic-model inspection evidence is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("semantic-model inspection evidence JSON root must be an object")
        return self.validate_report(payload)

    def validate_report(self, payload: dict[str, Any]) -> SemanticModelInspectionEvidenceBundle:
        """Validate exact report shape, governed identity and metadata-only invariants."""

        self._require_exact_keys(payload, _REPORT_KEYS, "semantic-model report")
        self._validate_report_contract(payload)
        source = self._require_governed_source(payload)

        logical_name = self._require_string(payload["logical_name"], "logical_name")
        if logical_name != source.logical_name:
            raise ValueError("semantic-model logical_name does not match governed source")

        provider_model_name = self._require_string(
            payload["provider_model_name"],
            "provider_model_name",
        )
        if provider_model_name != source.logical_name:
            raise ValueError("semantic-model provider_model_name does not match governed source")

        row_data_included = self._require_bool(
            payload["row_data_included"],
            "row_data_included",
        )
        expressions_included = self._require_bool(
            payload["expressions_included"],
            "expressions_included",
        )
        if row_data_included:
            raise ValueError("semantic-model inspection evidence must not contain row data")
        if expressions_included:
            raise ValueError("semantic-model inspection evidence must not contain expressions")

        raw_tables = self._require_list(payload["tables"], "tables")
        if not raw_tables:
            raise ValueError("semantic-model inspection evidence must contain at least one table")
        tables = tuple(
            self._validate_table(
                self._require_dict(item, f"tables[{index}]"),
                index=index,
            )
            for index, item in enumerate(raw_tables)
        )

        relationships = tuple(
            self._validate_relationship(
                self._require_dict(item, f"relationships[{index}]"),
                index=index,
            )
            for index, item in enumerate(
                self._require_list(payload["relationships"], "relationships")
            )
        )

        snapshot = IRRBBSemanticModelInspectionSnapshot(
            source_id=source.source_id,
            logical_name=logical_name,
            provider_workspace_reference=self._require_string(
                payload["provider_workspace_reference"],
                "provider_workspace_reference",
            ),
            provider_model_reference=self._require_string(
                payload["provider_model_reference"],
                "provider_model_reference",
            ),
            provider_model_name=provider_model_name,
            inspection_method=self._require_string(
                payload["inspection_method"],
                "inspection_method",
            ),
            observed_at=self._require_datetime(payload["observed_at"], "observed_at"),
            schema_freshness=self._require_schema_freshness(payload["schema_freshness"]),
            row_data_included=row_data_included,
            expressions_included=expressions_included,
            tables=tables,
            relationships=relationships,
        )
        return SemanticModelInspectionEvidenceBundle(source=source, snapshot=snapshot)

    @staticmethod
    def _validate_report_contract(payload: dict[str, Any]) -> None:
        report_type = SemanticModelInspectionEvidenceValidator._require_string(
            payload["report_type"],
            "report_type",
        )
        if report_type != SEMANTIC_MODEL_METADATA_REPORT_TYPE:
            raise ValueError("unsupported semantic-model inspection report_type")

        report_version = SemanticModelInspectionEvidenceValidator._require_string(
            payload["report_version"],
            "report_version",
        )
        if report_version != SEMANTIC_MODEL_INSPECTION_REPORT_VERSION:
            raise ValueError("unsupported semantic-model inspection report_version")

    @staticmethod
    def _require_governed_source(payload: dict[str, Any]) -> IRRBBPhysicalSourceDescriptor:
        source_id = SemanticModelInspectionEvidenceValidator._require_string(
            payload["source_id"],
            "source_id",
        )
        try:
            return _GOVERNED_SEMANTIC_MODEL_SOURCES[source_id]
        except KeyError as exc:
            raise ValueError(
                "semantic-model source_id is not a governed Power BI RTILB source"
            ) from exc

    @staticmethod
    def _validate_table(
        payload: dict[str, Any],
        *,
        index: int,
    ) -> IRRBBSemanticModelTableMetadata:
        context = f"tables[{index}]"
        SemanticModelInspectionEvidenceValidator._require_exact_keys(
            payload,
            _TABLE_KEYS,
            context,
        )
        columns = tuple(
            SemanticModelInspectionEvidenceValidator._validate_column(
                SemanticModelInspectionEvidenceValidator._require_dict(
                    item,
                    f"{context}.columns[{column_index}]",
                ),
                context=f"{context}.columns[{column_index}]",
            )
            for column_index, item in enumerate(
                SemanticModelInspectionEvidenceValidator._require_list(
                    payload["columns"],
                    f"{context}.columns",
                )
            )
        )
        if not columns:
            raise ValueError(f"{context}.columns must contain at least one column")

        measures = tuple(
            SemanticModelInspectionEvidenceValidator._validate_measure(
                SemanticModelInspectionEvidenceValidator._require_dict(
                    item,
                    f"{context}.measures[{measure_index}]",
                ),
                context=f"{context}.measures[{measure_index}]",
            )
            for measure_index, item in enumerate(
                SemanticModelInspectionEvidenceValidator._require_list(
                    payload["measures"],
                    f"{context}.measures",
                )
            )
        )
        return IRRBBSemanticModelTableMetadata(
            name=SemanticModelInspectionEvidenceValidator._require_string(
                payload["name"],
                f"{context}.name",
            ),
            is_hidden=SemanticModelInspectionEvidenceValidator._require_optional_bool(
                payload["is_hidden"],
                f"{context}.is_hidden",
            ),
            columns=columns,
            measures=measures,
        )

    @staticmethod
    def _validate_column(
        payload: dict[str, Any],
        *,
        context: str,
    ) -> IRRBBSemanticModelColumnMetadata:
        SemanticModelInspectionEvidenceValidator._require_exact_keys(
            payload,
            _COLUMN_KEYS,
            context,
        )
        return IRRBBSemanticModelColumnMetadata(
            name=SemanticModelInspectionEvidenceValidator._require_string(
                payload["name"],
                f"{context}.name",
            ),
            data_type=SemanticModelInspectionEvidenceValidator._require_string(
                payload["data_type"],
                f"{context}.data_type",
            ),
            is_hidden=SemanticModelInspectionEvidenceValidator._require_optional_bool(
                payload["is_hidden"],
                f"{context}.is_hidden",
            ),
        )

    @staticmethod
    def _validate_measure(
        payload: dict[str, Any],
        *,
        context: str,
    ) -> IRRBBSemanticModelMeasureMetadata:
        SemanticModelInspectionEvidenceValidator._require_exact_keys(
            payload,
            _MEASURE_KEYS,
            context,
        )
        return IRRBBSemanticModelMeasureMetadata(
            name=SemanticModelInspectionEvidenceValidator._require_string(
                payload["name"],
                f"{context}.name",
            ),
            is_hidden=SemanticModelInspectionEvidenceValidator._require_optional_bool(
                payload["is_hidden"],
                f"{context}.is_hidden",
            ),
        )

    @staticmethod
    def _validate_relationship(
        payload: dict[str, Any],
        *,
        index: int,
    ) -> IRRBBSemanticModelRelationshipMetadata:
        context = f"relationships[{index}]"
        SemanticModelInspectionEvidenceValidator._require_exact_keys(
            payload,
            _RELATIONSHIP_KEYS,
            context,
        )
        return IRRBBSemanticModelRelationshipMetadata(
            name=SemanticModelInspectionEvidenceValidator._require_optional_string(
                payload["name"],
                f"{context}.name",
            ),
            from_table=SemanticModelInspectionEvidenceValidator._require_string(
                payload["from_table"],
                f"{context}.from_table",
            ),
            from_column=SemanticModelInspectionEvidenceValidator._require_string(
                payload["from_column"],
                f"{context}.from_column",
            ),
            to_table=SemanticModelInspectionEvidenceValidator._require_string(
                payload["to_table"],
                f"{context}.to_table",
            ),
            to_column=SemanticModelInspectionEvidenceValidator._require_string(
                payload["to_column"],
                f"{context}.to_column",
            ),
            is_active=SemanticModelInspectionEvidenceValidator._require_optional_bool(
                payload["is_active"],
                f"{context}.is_active",
            ),
            cross_filter_direction=(
                SemanticModelInspectionEvidenceValidator._require_optional_string(
                    payload["cross_filter_direction"],
                    f"{context}.cross_filter_direction",
                )
            ),
            from_cardinality=(
                SemanticModelInspectionEvidenceValidator._require_optional_string(
                    payload["from_cardinality"],
                    f"{context}.from_cardinality",
                )
            ),
            to_cardinality=SemanticModelInspectionEvidenceValidator._require_optional_string(
                payload["to_cardinality"],
                f"{context}.to_cardinality",
            ),
        )

    @staticmethod
    def _require_schema_freshness(value: Any) -> IRRBBSemanticModelSchemaFreshness:
        text = SemanticModelInspectionEvidenceValidator._require_string(
            value,
            "schema_freshness",
        )
        try:
            return IRRBBSemanticModelSchemaFreshness(text)
        except ValueError as exc:
            raise ValueError("unsupported semantic-model schema_freshness") from exc

    @staticmethod
    def _require_datetime(value: Any, field_name: str) -> datetime:
        text = SemanticModelInspectionEvidenceValidator._require_string(value, field_name)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
        return parsed

    @staticmethod
    def _require_exact_keys(
        payload: dict[str, Any],
        expected: frozenset[str],
        context: str,
    ) -> None:
        actual = frozenset(payload)
        if actual == expected:
            return
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unknown:
            details.append(f"unknown={unknown}")
        raise ValueError(f"{context} has invalid shape: {', '.join(details)}")

    @staticmethod
    def _require_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-blank string")
        return value

    @staticmethod
    def _require_optional_string(value: Any, field_name: str) -> str | None:
        if value is None:
            return None
        return SemanticModelInspectionEvidenceValidator._require_string(value, field_name)

    @staticmethod
    def _require_bool(value: Any, field_name: str) -> bool:
        if type(value) is not bool:
            raise ValueError(f"{field_name} must be a boolean")
        return value

    @staticmethod
    def _require_optional_bool(value: Any, field_name: str) -> bool | None:
        if value is None:
            return None
        return SemanticModelInspectionEvidenceValidator._require_bool(value, field_name)

    @staticmethod
    def _require_list(value: Any, field_name: str) -> list[Any]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        return value

    @staticmethod
    def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be an object")
        return value
