from __future__ import annotations

import json

import pytest

from aip.product.configured.irrbb.physical_source_registry import (
    CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.semantic_model_inspection_evidence import (
    SemanticModelInspectionEvidenceValidator,
)
from aip.product.configured.irrbb.semantic_model_inspection_report_contract import (
    SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
    SEMANTIC_MODEL_METADATA_REPORT_TYPE,
)


def _payload(
    *,
    source_id: str = CREDIT_SEMANTIC_MODEL_SOURCE.source_id,
    logical_name: str = CREDIT_SEMANTIC_MODEL_SOURCE.logical_name,
    provider_model_name: str = CREDIT_SEMANTIC_MODEL_SOURCE.logical_name,
) -> dict[str, object]:
    return {
        "report_type": SEMANTIC_MODEL_METADATA_REPORT_TYPE,
        "report_version": SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
        "source_id": source_id,
        "logical_name": logical_name,
        "provider_workspace_reference": "workspace-runtime-reference",
        "provider_model_reference": "model-runtime-reference",
        "provider_model_name": provider_model_name,
        "inspection_method": "provider-metadata-scan",
        "observed_at": "2026-09-10T16:50:00-06:00",
        "schema_freshness": "CURRENT",
        "row_data_included": False,
        "expressions_included": False,
        "tables": [
            {
                "name": "Operations",
                "is_hidden": False,
                "columns": [
                    {"name": "OperationId", "data_type": "String", "is_hidden": False},
                    {"name": "CustomerId", "data_type": "String", "is_hidden": False},
                ],
                "measures": [{"name": "OperationCount", "is_hidden": False}],
            },
            {
                "name": "Customers",
                "is_hidden": False,
                "columns": [
                    {"name": "CustomerId", "data_type": "String", "is_hidden": False}
                ],
                "measures": [],
            },
        ],
        "relationships": [
            {
                "name": "OperationsCustomers",
                "from_table": "Operations",
                "from_column": "CustomerId",
                "to_table": "Customers",
                "to_column": "CustomerId",
                "is_active": True,
                "cross_filter_direction": "Single",
                "from_cardinality": "Many",
                "to_cardinality": "One",
            }
        ],
    }


def test_validator_binds_credit_metadata_to_governed_source() -> None:
    bundle = SemanticModelInspectionEvidenceValidator().validate_report(_payload())

    assert bundle.source is CREDIT_SEMANTIC_MODEL_SOURCE
    assert bundle.snapshot.source_id == CREDIT_SEMANTIC_MODEL_SOURCE.source_id
    assert bundle.snapshot.provider_model_name == "Credito"
    assert len(bundle.snapshot.tables) == 2
    assert len(bundle.snapshot.relationships) == 1


def test_validator_binds_term_deposit_metadata_to_governed_source() -> None:
    payload = _payload(
        source_id=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.source_id,
        logical_name=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.logical_name,
        provider_model_name=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.logical_name,
    )

    bundle = SemanticModelInspectionEvidenceValidator().validate_report(payload)

    assert bundle.source is TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE
    assert bundle.snapshot.logical_name == "Certificados"


def test_parse_json_document_validates_complete_transferred_report() -> None:
    bundle = SemanticModelInspectionEvidenceValidator().parse_json_document(
        json.dumps(_payload())
    )

    assert bundle.snapshot.row_data_included is False
    assert bundle.snapshot.expressions_included is False


def test_validator_rejects_unknown_top_level_fields() -> None:
    payload = _payload()
    payload["unexpected"] = "not-allowed"

    with pytest.raises(ValueError, match="unknown=.*unexpected"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_unknown_semantic_model_source() -> None:
    payload = _payload(source_id="unregistered.semantic.model")

    with pytest.raises(ValueError, match="not a governed Power BI RTILB source"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_logical_name_mismatch() -> None:
    payload = _payload(logical_name="OtherModel")

    with pytest.raises(ValueError, match="logical_name does not match"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_provider_model_name_mismatch() -> None:
    payload = _payload(provider_model_name="OtherModel")

    with pytest.raises(ValueError, match="provider_model_name does not match"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        ("row_data_included", "must not contain row data"),
        ("expressions_included", "must not contain expressions"),
    ],
)
def test_validator_rejects_content_outside_metadata_boundary(
    field_name: str,
    message: str,
) -> None:
    payload = _payload()
    payload[field_name] = True

    with pytest.raises(ValueError, match=message):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_naive_observation_timestamp() -> None:
    payload = _payload()
    payload["observed_at"] = "2026-09-10T16:50:00"

    with pytest.raises(ValueError, match="timezone-aware"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_unsupported_schema_freshness() -> None:
    payload = _payload()
    payload["schema_freshness"] = "ASSUMED_CURRENT"

    with pytest.raises(ValueError, match="unsupported semantic-model schema_freshness"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_relationship_to_unobserved_column() -> None:
    payload = _payload()
    relationships = payload["relationships"]
    assert isinstance(relationships, list)
    relationship = relationships[0]
    assert isinstance(relationship, dict)
    relationship["to_column"] = "MissingColumn"

    with pytest.raises(ValueError, match="unknown to-column"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)


def test_validator_rejects_nested_unknown_fields() -> None:
    payload = _payload()
    tables = payload["tables"]
    assert isinstance(tables, list)
    table = tables[0]
    assert isinstance(table, dict)
    columns = table["columns"]
    assert isinstance(columns, list)
    column = columns[0]
    assert isinstance(column, dict)
    column["rtlib_alias"] = "principal"

    with pytest.raises(ValueError, match="unknown=.*rtlib_alias"):
        SemanticModelInspectionEvidenceValidator().validate_report(payload)
