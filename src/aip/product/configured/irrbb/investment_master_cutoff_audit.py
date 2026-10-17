"""Read-only investment-master source evidence for the RTILB screen.

Uses only the exact-cutoff institutional master and its *original* source currency.
No CRC fallback, no FX conversion, no fabricated maturity payments or coupons.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
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
        value = (
            value.replace(".", "").replace(",", ".")
            if value.rfind(",") > value.rfind(".")
            else value.replace(",", "")
        )
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
    source_reader = reader or InstitutionalPortfolioMasterReader()
    reading = source_reader.read(source_path, valuation_date_override=cutoff, diagnostic_mode=False)
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
    # The reader stores source_values under *normalized* source headers, while
    # detected_column_mapping preserves the workbook's original header spelling.
    principal_key = source_reader._normalize_header(principal_header) if principal_header else None
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
    bands: dict[tuple[str, int, str], dict[str, int | Decimal]] = defaultdict(
        lambda: {"positions": 0, "source_principal": Decimal(0)}
    )
    excluded: dict[tuple[str, str], dict[str, int | Decimal]] = defaultdict(
        lambda: {"positions": 0, "valid_source_principal": Decimal(0)}
    )
    eligible_amounts: dict[str, Decimal] = defaultdict(Decimal)
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
            source_values.get(principal_key)
            if principal_key and isinstance(source_values, dict)
            else None
        )
        principal = _source_number(source_value)
        if principal is None or not raw_currency:
            group["principal_missing"] += 1
        else:
            group["principal_records"] += 1
            group["source_principal"] += principal
            eligible_amounts[currency] += principal

        if raw_currency not in {"CRC", "USD"}:
            reason = "MISSING_NATIVE_CURRENCY" if not raw_currency else "UNSUPPORTED_CURRENCY"
        elif principal is None:
            reason = "INVALID_OR_MISSING_SOURCE_PRINCIPAL"
        elif not isinstance(maturity, date) or maturity < cutoff:
            reason = "MISSING_OR_PAST_MATURITY"
        else:
            assignment = IRRBBTimeBucketService.assign(
                valuation_date=cutoff, risk_date=maturity
            )
            assigned = bands[(currency, assignment.ordinal, assignment.label)]
            assigned["positions"] += 1
            assigned["source_principal"] += principal
            continue

        discarded = excluded[(currency, reason)]
        discarded["positions"] += 1
        if principal is not None and raw_currency in {"CRC", "USD"}:
            discarded["valid_source_principal"] += principal

    observed_amounts: dict[str, Decimal] = defaultdict(Decimal)
    excluded_amounts: dict[str, Decimal] = defaultdict(Decimal)
    for (currency, _ordinal, _label), band in bands.items():
        observed_amounts[currency] += band["source_principal"]
    for (currency, _reason), entry in excluded.items():
        excluded_amounts[currency] += entry["valid_source_principal"]
    if any(
        observed_amounts[currency] + excluded_amounts[currency] != amount
        for currency, amount in eligible_amounts.items()
    ):
        raise ValueError("Investment maturity principal does not reconcile by native currency")
    if sum(band["positions"] for band in bands.values()) + sum(
        item["positions"] for item in excluded.values()
    ) != len(reading.normalized_positions):
        raise ValueError("Investment maturity classification count is incomplete")

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
        "maturity_bands": [
            {
                "source_currency": currency,
                "ordinal": ordinal,
                "band": label,
                "positions": int(group["positions"]),
                "source_principal": str(group["source_principal"]),
            }
            for (currency, ordinal, label), group in sorted(bands.items())
        ],
        "maturity_exclusions": [
            {
                "source_currency": currency,
                "reason": reason,
                "positions": int(item["positions"]),
                "valid_source_principal": str(item["valid_source_principal"]),
            }
            for (currency, reason), item in sorted(excluded.items())
        ],
        "maturity_reconciliation": [
            {
                "source_currency": currency,
                "eligible_source_principal": str(eligible_amounts[currency]),
                "observed_principal": str(observed_amounts[currency]),
                "excluded_valid_principal": str(excluded_amounts[currency]),
                "difference": "0",
            }
            for currency in sorted(eligible_amounts)
        ],
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
            "Observed institutional master maturity buckets, not cashflow schedules, repricing or 19-band GAP. "
            "No FX conversion. Source-column principal only; other balance fields are not substituted. "
            "The cutoff comes from the filename and is not independently certified."
        ),
    }
