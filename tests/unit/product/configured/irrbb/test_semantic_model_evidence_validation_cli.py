from __future__ import annotations

import hashlib
import json
from io import StringIO
from pathlib import Path

from aip.product.configured.irrbb.physical_source_registry import (
    CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.semantic_model_evidence_validation_cli import run
from aip.product.configured.irrbb.semantic_model_inspection_report_contract import (
    SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
    SEMANTIC_MODEL_METADATA_REPORT_TYPE,
)

_WORKSPACE_REFERENCE = "workspace-runtime-reference"
_MODEL_REFERENCE = "model-runtime-reference"


def _payload(
    *,
    term_deposit: bool = False,
    schema_freshness: str = "CURRENT",
) -> dict[str, object]:
    source = TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE if term_deposit else CREDIT_SEMANTIC_MODEL_SOURCE
    return {
        "report_type": SEMANTIC_MODEL_METADATA_REPORT_TYPE,
        "report_version": SEMANTIC_MODEL_INSPECTION_REPORT_VERSION,
        "source_id": source.source_id,
        "logical_name": source.logical_name,
        "provider_workspace_reference": _WORKSPACE_REFERENCE,
        "provider_model_reference": _MODEL_REFERENCE,
        "provider_model_name": source.logical_name,
        "inspection_method": "provider-metadata-scan",
        "observed_at": "2026-09-14T08:30:00-06:00",
        "schema_freshness": schema_freshness,
        "row_data_included": False,
        "expressions_included": False,
        "tables": [
            {
                "name": "Operations",
                "is_hidden": False,
                "columns": [
                    {"name": "OperationId", "data_type": "String", "is_hidden": False},
                    {"name": "Balance", "data_type": "Decimal", "is_hidden": False},
                ],
                "measures": [{"name": "OperationCount", "is_hidden": False}],
            },
            {
                "name": "Calendar",
                "is_hidden": False,
                "columns": [{"name": "Date", "data_type": "Date", "is_hidden": False}],
                "measures": [],
            },
        ],
        "relationships": [],
    }


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "semantic-model-evidence.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_credit_metadata_evidence_validates_without_echoing_provider_references(
    tmp_path: Path,
) -> None:
    evidence_path = _write_payload(tmp_path, _payload())
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--evidence-json",
            str(evidence_path),
            "--expected-segment",
            "CREDIT",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 0
    assert stderr.getvalue() == ""
    report = json.loads(stdout.getvalue())
    assert report["validation_status"] == "VALIDATED_METADATA_ONLY"
    assert report["segment"] == "CREDIT"
    assert report["logical_name"] == "Credito"
    assert report["table_count"] == 2
    assert report["column_count"] == 3
    assert report["measure_count"] == 1
    assert report["relationship_count"] == 0
    assert report["production_activation_authorized"] is False
    assert report["provider_workspace_reference_fingerprint"] == (
        "sha256:" + hashlib.sha256(_WORKSPACE_REFERENCE.encode("utf-8")).hexdigest()
    )
    assert _WORKSPACE_REFERENCE not in stdout.getvalue()
    assert _MODEL_REFERENCE not in stdout.getvalue()
    assert str(tmp_path) not in stdout.getvalue()


def test_term_deposit_evidence_can_be_bound_to_expected_segment(tmp_path: Path) -> None:
    evidence_path = _write_payload(tmp_path, _payload(term_deposit=True))
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--evidence-json",
            str(evidence_path),
            "--expected-segment",
            "TERM_DEPOSIT",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 0
    assert json.loads(stdout.getvalue())["logical_name"] == "Certificados"
    assert stderr.getvalue() == ""


def test_expected_segment_mismatch_fails_closed(tmp_path: Path) -> None:
    evidence_path = _write_payload(tmp_path, _payload())
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--evidence-json",
            str(evidence_path),
            "--expected-segment",
            "TERM_DEPOSIT",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert "does not match --expected-segment" in stderr.getvalue()


def test_require_current_schema_returns_three_after_rendering_validated_summary(
    tmp_path: Path,
) -> None:
    evidence_path = _write_payload(tmp_path, _payload(schema_freshness="MAY_BE_STALE"))
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        [
            "--evidence-json",
            str(evidence_path),
            "--require-current-schema",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 3
    report = json.loads(stdout.getvalue())
    assert report["schema_freshness"] == "MAY_BE_STALE"
    assert report["production_activation_authorized"] is False
    assert stderr.getvalue() == ""


def test_row_data_or_unknown_credential_fields_are_rejected(tmp_path: Path) -> None:
    row_data_payload = _payload()
    row_data_payload["row_data_included"] = True
    row_data_path = _write_payload(tmp_path, row_data_payload)
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--evidence-json", str(row_data_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert "must not contain row data" in stderr.getvalue()

    credential_payload = _payload()
    credential_payload["access_token"] = "must-never-be-accepted"
    credential_path = _write_payload(tmp_path, credential_payload)
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--evidence-json", str(credential_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert "unknown=['access_token']" in stderr.getvalue()
    assert "must-never-be-accepted" not in stderr.getvalue()


def test_file_access_failure_does_not_echo_local_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "private" / "missing.json"
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--evidence-json", str(missing_path)],
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "IRRBB semantic-model evidence validation failed: evidence file access error\n"
    )
    assert str(tmp_path) not in stderr.getvalue()
