from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NoReturn, TextIO

from aip.product.configured.adapters.institutional_portfolio_scenario_adapter import (
    InstitutionalMasterScenarioRiskAdapter,
)
from aip.product.configured.irrbb.investment_source_rules import InvestmentMasterSourceRules
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
    InstitutionalPortfolioMasterReadResult,
)

REPORT_TYPE = "INSTITUTIONAL_PORTFOLIO_SCENARIO_SOURCE_READINESS"
REPORT_VERSION = "2026.10.12"
EXTERNAL_EVIDENCE = (
    "APPROVED_REGULATORY_EXPOSURES",
    "APPROVED_INVESTMENT_POLICY",
    "INDEPENDENT_TOTAL_RETURN_HISTORIES",
)


class _UsageError(ValueError):
    """CLI usage diagnostics that never print file contents."""


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() and result > 0 else None


def summarize_native_master(result: InstitutionalPortfolioMasterReadResult) -> dict[str, object]:
    """Non-sensitive source-readiness summary. Never emit positions or monetary values."""
    issues: set[str] = set()
    native = set(result.detected_column_mapping)
    required = set(InstitutionalMasterScenarioRiskAdapter._REQUIRED_NATIVE_COLUMNS)
    missing = sorted((required | {"contract_number"}).difference(native))
    if missing:
        issues.add("NATIVE_COLUMNS_MISSING")
    if result.source_status != "HEALTHY" or result.warnings or result.rejected_row_count:
        issues.add("MASTER_READER_DEGRADED")
    if not result.normalized_positions or not result.sheet_selected.strip():
        issues.add("MASTER_EMPTY_OR_SHEET_UNKNOWN")
    identities: set[str] = set()
    source_rows: set[int] = set()
    currencies: set[str] = set()
    for position in result.normalized_positions:
        row_number = position.get("source_row")
        if type(row_number) is not int or row_number <= 0 or row_number in source_rows:
            issues.add("SOURCE_ROW_IDENTITY_INVALID")
        else:
            source_rows.add(row_number)
        contract = str(position.get("contract_number") or "").strip()
        isin = str(position.get("isin") or "").strip()
        key = InvestmentMasterSourceRules.stable_position_id(
            contract_number=contract,
            isin=isin,
            series=position.get("series"),
        )
        if not contract or not isin or key is None or key in identities:
            issues.add("CONTRACT_ISIN_IDENTITY_INVALID")
        elif key is not None:
            identities.add(key)
        currency = str(position.get("source_currency") or "").strip().upper()
        if currency not in {"CRC", "USD"}:
            issues.add("NATIVE_CURRENCY_UNSUPPORTED")
        else:
            currencies.add(currency)
        local = _decimal(position.get("market_value"))
        crc = _decimal(position.get("market_value_crc"))
        if local is None or crc is None:
            issues.add("MARKET_VALUES_INVALID")
        elif currency == "CRC" and abs(local - crc) > Decimal("0.01"):
            issues.add("CRC_NATIVE_VALUATION_MISMATCH")
    pending = list(EXTERNAL_EVIDENCE)
    if "USD" in currencies:
        pending.append("APPROVED_HISTORICAL_FX_CONVERSION")
    return {
        "report_type": REPORT_TYPE,
        "report_version": REPORT_VERSION,
        "valuation_cutoff": result.valuation_date.isoformat(),
        "sheet_selected": result.sheet_selected,
        "accepted_position_count": len(result.normalized_positions),
        "rejected_row_count": result.rejected_row_count,
        "warning_count": len(result.warnings),
        "currencies_present": sorted(currencies),
        "missing_native_columns": missing,
        "blocking_codes": sorted(issues),
        "source_structural_ready": not issues,
        "pending_independent_evidence": pending,
        "scenario_ready": False,
        "production_activation_authorized": False,
    }


def inspect(
    path: Path,
    *,
    cutoff: date,
    reader: InstitutionalPortfolioMasterReader | None = None,
) -> dict[str, object]:
    """Inspect one dated XLSX without copying confidential lot or valuation details."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Institutional master is not a regular file")
    matches = list(InstitutionalMasterScenarioRiskAdapter._DATED_FILENAME.finditer(path.stem))
    if len(matches) != 1:
        raise ValueError("Institutional master filename cutoff is ambiguous")
    match = matches[0]
    if date(
        int(match.group("year")), int(match.group("month")), int(match.group("day"))
    ) != cutoff:
        raise ValueError("Institutional master filename has a different cutoff")
    before = InstitutionalMasterScenarioRiskAdapter._file_sha256(path)
    source_reader = reader if reader is not None else InstitutionalPortfolioMasterReader()
    result = source_reader.read(path, valuation_date_override=cutoff)
    if InstitutionalMasterScenarioRiskAdapter._file_sha256(path) != before:
        raise ValueError("Institutional master changed during inspection")
    if result.valuation_date != cutoff:
        raise ValueError("Institutional master reader cutoff differs from request")
    report = summarize_native_master(result)
    report["source_file_name"] = path.name
    report["master_sha256"] = before
    return report


def _parser() -> _SafeParser:
    parser = _SafeParser(
        prog="portfolio-scenario-readiness",
        description="Read-only structural diagnostics; no source positions or balances emitted.",
    )
    parser.add_argument("--path", required=True, help="Dated institutional master XLSX file")
    parser.add_argument("--cutoff", required=True, help="Expected cutoff in YYYY-MM-DD")
    parser.add_argument(
        "--require-source-ready",
        action="store_true",
        help="Return code 3 if native source structure is blocked (not scenario certification)",
    )
    return parser


def run(
    argv: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    reader: InstitutionalPortfolioMasterReader | None = None,
) -> int:
    try:
        args = _parser().parse_args(tuple(argv))
        cutoff = date.fromisoformat(args.cutoff)
        report = inspect(Path(args.path), cutoff=cutoff, reader=reader)
        json.dump(report, stdout, indent=2, sort_keys=True, ensure_ascii=False)
        stdout.write("\n")
        if args.require_source_ready and not report["source_structural_ready"]:
            return 3
        return 0
    except (_UsageError, ValueError, OSError, RuntimeError):
        stderr.write("Portfolio scenario readiness failed: invalid arguments or source evidence\n")
        return 2


def main() -> int:
    return run(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
