"""Read-only investment-master source evidence for the RTILB screen.

Uses only the exact-cutoff institutional master and its *original* source currency.
No CRC fallback, no FX conversion, no fabricated maturity payments or coupons.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aip.product.configured.configuration.configured_source_config import FolderWatchSourceConfig
from aip.product.configured.irrbb.investment_master_discovery import (
    resolve_exact_cutoff_master,
)
from aip.product.configured.irrbb.investment_source_evidence import (
    InvestmentMasterSourceEvidenceAssessor,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)


def _source_number(raw: object) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    value = str(raw).strip()
    if not value:
        return None
    value = value.replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".") if value.rfind(",") > value.rfind(".") else value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def inspect_investment_master_cutoff(
    *,
    cutoff: date,
    folder: FolderWatchSourceConfig,
    reader: InstitutionalPortfolioMasterReader | None = None,
) -> dict[str, object]:
    """Audit source completeness, not contractual payment-band eligibility."""
    if not folder.enabled:
        return {"status": "INVESTMENT_SOURCE_DISABLED", "cutoff": cutoff.isoformat()}
    status, source_path, candidates = resolve_exact_cutoff_master(
        folder.portfolio_root, folder.portfolio_master_pattern, cutoff
    )
    if source_path is None:
        return {
            "status": status,
            "cutoff": cutoff.isoformat(),
            "matching_master_count": candidates,
            "certified": False,
        }
    reading = (reader or InstitutionalPortfolioMasterReader()).read(
        source_path, valuation_date_override=cutoff, diagnostic_mode=False
    )
    if reading.source_status == "UNAVAILABLE" or not reading.normalized_positions:
        return {
            "status": "INVESTMENT_MASTER_UNREADABLE",
            "cutoff": cutoff.isoformat(),
            "matching_master_count": 1,
            "certified": False,
        }
    certification = InvestmentMasterSourceEvidenceAssessor.assess(reading)
    source_columns = reading.detected_column_mapping
    principal_header = source_columns.get("principal_balance")
    grouped: dict[str, dict[str, int | Decimal]] = defaultdict(
        lambda: {
            "positions": 0,
            "principal_records": 0,
            "principal_missing": 0,
            "source_principal": Decimal(0),
            "maturity_present": 0,
            "maturity_missing_or_past": 0,
        }
    )
    for position in reading.normalized_positions:
        raw_currency = str(position.get("source_currency") or "").strip().upper()
        # The general portfolio reader may fill a missing currency with CRC.
        # That fallback MUST NOT become financial RTILB evidence.
        currency = raw_currency or "(SIN MONEDA NATIVA)"
        group = grouped[currency]
        group["positions"] += 1
        maturity = position.get("maturity_date")
        if isinstance(maturity, date) and maturity >= cutoff:
            group["maturity_present"] += 1
        else:
            group["maturity_missing_or_past"] += 1
        source_values = position.get("source_values")
        source_value = (
            source_values.get(principal_header)
            if principal_header and isinstance(source_values, dict)
            else None
        )
        principal = _source_number(source_value)
        if principal is None or not raw_currency:
            group["principal_missing"] += 1
        else:
            group["principal_records"] += 1
            group["source_principal"] += principal
    return {
        "status": "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED",
        "cutoff": cutoff.isoformat(),
        "master_filename": Path(source_path).name,
        "matching_master_count": candidates,
        "filename_cutoff_only": True,
        "reader_status": reading.source_status,
        "accepted_positions": len(reading.normalized_positions),
        "rejected_rows": reading.rejected_row_count,
        "warning_count": len(reading.warnings),
        "principal_column_detected": principal_header is not None,
        "certification_status": certification.status.value,
        "blocking_requirements": list(certification.blocking_requirement_ids),
        "not_assessed_requirements": list(certification.not_assessed_requirement_ids),
        "certified": False,
        "currencies": [
            {
                "source_currency": currency,
                "positions": int(group["positions"]),
                "principal_records": int(group["principal_records"]),
                "principal_missing": int(group["principal_missing"]),
                "source_principal": str(group["source_principal"]),
                "maturity_present": int(group["maturity_present"]),
                "maturity_missing_or_past": int(group["maturity_missing_or_past"]),
            }
            for currency, group in sorted(grouped.items())
        ],
        "note": (
            "Observed institutional master positions, not cashflow schedules or 19-band GAP. "
            "No FX conversion. Source-column principal only; other balance fields are not substituted. "
            "The cutoff comes from the filename and is not independently certified."
        ),
    }
