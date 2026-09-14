from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn, TextIO

from aip.application.irrbb.source_certification import IRRBBSourceCertificationReport
from aip.product.configured.irrbb.investment_source_evidence import (
    InvestmentMasterSourceEvidenceAssessor,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
    InstitutionalPortfolioMasterReader,
)

INVESTMENT_READINESS_REPORT_TYPE = "IRRBB_INVESTMENT_SOURCE_READINESS"
INVESTMENT_READINESS_REPORT_VERSION = "2026.09.14"


class _CLIUsageError(ValueError):
    """Safe command-line usage failure without argparse process termination."""


class _SafeArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports usage errors through the CLI return contract."""

    def error(self, message: str) -> NoReturn:
        raise _CLIUsageError(message)


def investment_readiness_report(
    result: InstitutionalPortfolioMasterReadResult,
    certification: IRRBBSourceCertificationReport,
) -> dict[str, object]:
    """Render a non-contractual readiness summary for the investment source candidate."""

    requirement_by_id = {
        requirement.requirement_id: requirement
        for requirement in certification.profile.requirements
    }
    source_file_name = Path(result.source_file).name if result.source_file else ""
    return {
        "report_type": INVESTMENT_READINESS_REPORT_TYPE,
        "report_version": INVESTMENT_READINESS_REPORT_VERSION,
        "source_reference": InvestmentMasterSourceEvidenceAssessor.SOURCE_REFERENCE,
        "source_file_name": source_file_name,
        "reader_valuation_date": result.valuation_date.isoformat(),
        "sheet_selected": result.sheet_selected,
        "source_status": result.source_status,
        "accepted_position_count": len(result.normalized_positions),
        "rejected_row_count": result.rejected_row_count,
        "warning_count": len(result.warnings),
        "detected_canonical_fields": sorted(result.detected_column_mapping),
        "requirement_profile": {
            "code": certification.profile.code,
            "version": certification.profile.version,
            "effective_from": certification.profile.effective_from.isoformat(),
            "source_reference": certification.profile.source_reference,
        },
        "certification_status": certification.status.value,
        "blocking_requirement_ids": list(certification.blocking_requirement_ids),
        "not_assessed_requirement_ids": list(certification.not_assessed_requirement_ids),
        "production_activation_authorized": False,
        "requirements": [
            {
                "requirement_id": item.requirement_id,
                "canonical_variable": requirement_by_id[item.requirement_id].canonical_variable,
                "status": item.status.value,
                "source_reference": item.source_reference,
                "derivation_rule_reference": item.derivation_rule_reference,
                "supplementary_source_reference": item.supplementary_source_reference,
                "evidence_reference": item.evidence_reference,
                "notes": item.notes,
            }
            for item in certification.assessments
        ],
    }


def _build_parser() -> _SafeArgumentParser:
    parser = _SafeArgumentParser(
        prog="irrbb-investment-readiness",
        description=(
            "Assess an institutional portfolio master against the governed RTILB "
            "investment source requirements without emitting contractual position rows."
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the governed institutional portfolio master workbook.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return exit code 3 when the source certification result is not READY.",
    )
    return parser


def _write_report(report: dict[str, object], *, stdout: TextIO) -> None:
    json.dump(report, stdout, ensure_ascii=False, indent=2, sort_keys=True)
    stdout.write("\n")


def run(
    argv: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    reader: InstitutionalPortfolioMasterReader | None = None,
) -> int:
    """Read one governed master, assess evidence and return a process-style status."""

    try:
        args = _build_parser().parse_args(tuple(argv))
        source_reader = reader if reader is not None else InstitutionalPortfolioMasterReader()
        result = source_reader.read(args.path, diagnostic_mode=False)
        certification = InvestmentMasterSourceEvidenceAssessor.assess(result)
        _write_report(
            investment_readiness_report(result, certification),
            stdout=stdout,
        )
        if args.require_ready and not certification.is_ready:
            return 3
        return 0
    except _CLIUsageError as exc:
        stderr.write(f"IRRBB investment readiness usage error: {exc}\n")
        return 2
    except (OSError, RuntimeError, ValueError):
        stderr.write("IRRBB investment readiness failed: source assessment error\n")
        return 1


def main() -> int:
    """Run the fail-closed investment source readiness diagnostic."""

    return run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
