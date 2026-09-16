from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn, TextIO

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceSegment
from aip.application.irrbb.semantic_model_inspection import IRRBBSemanticModelSchemaFreshness
from aip.product.configured.irrbb.semantic_model_inspection_evidence import (
    SemanticModelInspectionEvidenceBundle,
    SemanticModelInspectionEvidenceValidator,
)

SEMANTIC_MODEL_EVIDENCE_VALIDATION_REPORT_TYPE = "IRRBB_POWER_BI_SEMANTIC_MODEL_EVIDENCE_VALIDATION"
SEMANTIC_MODEL_EVIDENCE_VALIDATION_REPORT_VERSION = "2026.09.14"
_ALLOWED_SEGMENTS = (
    IRRBBPhysicalSourceSegment.CREDIT,
    IRRBBPhysicalSourceSegment.TERM_DEPOSIT,
)


class _CLIUsageError(ValueError):
    """Safe command-line usage failure without argparse process termination."""


class _SafeArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage errors through the CLI return contract."""

    def error(self, message: str) -> NoReturn:
        raise _CLIUsageError(message)


def semantic_model_evidence_validation_report(
    bundle: SemanticModelInspectionEvidenceBundle,
) -> dict[str, object]:
    """Render a non-secret validation summary without assigning RTILB semantics."""

    snapshot = bundle.snapshot
    return {
        "report_type": SEMANTIC_MODEL_EVIDENCE_VALIDATION_REPORT_TYPE,
        "report_version": SEMANTIC_MODEL_EVIDENCE_VALIDATION_REPORT_VERSION,
        "validation_status": "VALIDATED_METADATA_ONLY",
        "source_id": bundle.source.source_id,
        "segment": bundle.source.segment.value,
        "logical_name": bundle.source.logical_name,
        "inspection_method": snapshot.inspection_method,
        "observed_at": snapshot.observed_at.isoformat(),
        "schema_freshness": snapshot.schema_freshness.value,
        "provider_workspace_reference_fingerprint": _optional_reference_fingerprint(
            snapshot.provider_workspace_reference
        ),
        "provider_model_reference_fingerprint": _reference_fingerprint(
            snapshot.provider_model_reference
        ),
        "table_count": len(snapshot.tables),
        "column_count": sum(len(table.columns) for table in snapshot.tables),
        "measure_count": sum(len(table.measures) for table in snapshot.tables),
        "relationship_count": len(snapshot.relationships),
        "row_data_included": snapshot.row_data_included,
        "expressions_included": snapshot.expressions_included,
        "production_activation_authorized": False,
    }


def _reference_fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _optional_reference_fingerprint(value: str | None) -> str | None:
    if value is None:
        return None
    return _reference_fingerprint(value)


def _build_parser() -> _SafeArgumentParser:
    parser = _SafeArgumentParser(
        prog="irrbb-semantic-model-evidence-validation",
        description=(
            "Validate transferred Power BI semantic-model metadata evidence without "
            "reading row data, expressions, credentials or assigning RTILB business meaning."
        ),
    )
    parser.add_argument(
        "--evidence-json",
        required=True,
        help="Path to one governed semantic-model metadata evidence JSON document.",
    )
    parser.add_argument(
        "--expected-segment",
        choices=tuple(segment.value for segment in _ALLOWED_SEGMENTS),
        help="Optionally require CREDIT or TERM_DEPOSIT governed source identity.",
    )
    parser.add_argument(
        "--require-current-schema",
        action="store_true",
        help=(
            "Return exit code 3 when provider-reported schema freshness is not CURRENT. "
            "This is not production activation approval."
        ),
    )
    return parser


def _read_evidence(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _require_expected_segment(
    bundle: SemanticModelInspectionEvidenceBundle,
    expected_segment: str | None,
) -> None:
    if expected_segment is None:
        return
    expected = IRRBBPhysicalSourceSegment(expected_segment)
    if bundle.source.segment is not expected:
        raise ValueError("semantic-model evidence source does not match --expected-segment")


def _write_report(report: dict[str, object], *, stdout: TextIO) -> None:
    json.dump(report, stdout, ensure_ascii=False, indent=2, sort_keys=True)
    stdout.write("\n")


def run(
    argv: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Validate one transferred evidence document and return a process-style status."""

    try:
        args = _build_parser().parse_args(tuple(argv))
        bundle = SemanticModelInspectionEvidenceValidator().parse_json_document(
            _read_evidence(args.evidence_json)
        )
        _require_expected_segment(bundle, args.expected_segment)
        _write_report(semantic_model_evidence_validation_report(bundle), stdout=stdout)

        if (
            args.require_current_schema
            and bundle.snapshot.schema_freshness is not IRRBBSemanticModelSchemaFreshness.CURRENT
        ):
            return 3
        return 0
    except _CLIUsageError as exc:
        stderr.write(f"IRRBB semantic-model evidence usage error: {exc}\n")
        return 2
    except (json.JSONDecodeError, ValueError) as exc:
        stderr.write(f"IRRBB semantic-model evidence validation failed: {exc}\n")
        return 1
    except (FileNotFoundError, OSError):
        stderr.write(
            "IRRBB semantic-model evidence validation failed: evidence file access error\n"
        )
        return 1


def main() -> int:
    """Run the metadata-only semantic-model evidence validator."""

    return run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
