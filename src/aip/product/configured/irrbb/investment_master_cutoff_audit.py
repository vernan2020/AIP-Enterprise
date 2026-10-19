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


# Approved in this RTILB source adapter only. The source spelling remains
# reported independently and no conversion or currency inference is performed.
_EXPLICIT_MASTER_CURRENCY_ALIASES = {"DOLAR": "USD"}
_ALIAS_RULE_VERSION = "INV-MASTER-CURRENCY-ALIASES-V1"


def _audit_currency(raw_code: str) -> str:
    return _EXPLICIT_MASTER_CURRENCY_ALIASES.get(raw_code, raw_code or "(SIN MONEDA NATIVA)")


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
    original_codes: dict[tuple[str, str], dict[str, int | Decimal]] = defaultdict(
        lambda: {"positions": 0, "source_principal": Decimal(0)}
    )
    for position in reading.normalized_positions:
        raw_currency = str(position.get("source_currency") or "").strip().upper()
        # Never use the portfolio reader's default CRC when the source lacks currency.
        # Recognize only the explicitly controlled DOLAR -> USD alias.
        currency = _audit_currency(raw_currency)
        original_currency = raw_currency or "(SIN MONEDA NATIVA)"
        source_code = original_codes[(original_currency, currency)]
        source_code["positions"] += 1
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
        if principal is not None:
            source_code["source_principal"] += principal
        if principal is None or not raw_currency:
            group["principal_missing"] += 1
        else:
            group["principal_records"] += 1
            group["source_principal"] += principal
        if principal is not None:
            # Preserve positive numeric values under their original source code.
            # A missing/unsupported currency remains excluded, never inferred.
            eligible_amounts[currency] += principal

        if currency not in {"CRC", "USD"}:
            reason = "MISSING_NATIVE_CURRENCY" if not raw_currency else "UNSUPPORTED_CURRENCY"
        elif principal is None:
            reason = "INVALID_OR_MISSING_SOURCE_PRINCIPAL"
        elif not isinstance(maturity, date):
            reason = "MISSING_OR_INVALID_MATURITY"
        elif maturity < cutoff:
            reason = "PAST_MATURITY"
        else:
            assignment = IRRBBTimeBucketService.assign(valuation_date=cutoff, risk_date=maturity)
            assigned = bands[(currency, assignment.ordinal, assignment.label)]
            assigned["positions"] += 1
            assigned["source_principal"] += principal
            continue

        discarded = excluded[(currency, reason)]
        discarded["positions"] += 1
        if principal is not None:
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

    canonical_labels = (
        (1, "Overnight"),
        *(
            (ordinal, label)
            for ordinal, (_months, _bucket, label) in enumerate(
                IRRBBTimeBucketService._MONTH_BUCKETS, start=2
            )
        ),
        (19, "Más de 20 años"),
    )
    native_currencies = tuple(
        sorted(currency for currency in grouped if currency in {"CRC", "USD"})
    )
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
        "currency_mapping_rule": _ALIAS_RULE_VERSION,
        "source_currency_mappings": [
            {
                "source_currency": original,
                "normalized_currency": canonical,
                "mapping_status": (
                    "EXPLICIT_ALIAS"
                    if original in _EXPLICIT_MASTER_CURRENCY_ALIASES
                    else "EXACT_SOURCE_CODE"
                    if canonical in {"CRC", "USD"}
                    else "MISSING_SOURCE_CODE"
                    if original == "(SIN MONEDA NATIVA)"
                    else "UNSUPPORTED_SOURCE_CODE"
                ),
                "positions": int(group["positions"]),
                "source_principal": str(group["source_principal"]),
            }
            for (original, canonical), group in sorted(original_codes.items())
        ],
        "maturity_bands": [
            {
                "source_currency": currency,
                "ordinal": ordinal,
                "band": label,
                "positions": int(bands.get((currency, ordinal, label), {}).get("positions", 0)),
                "source_principal": str(
                    bands.get((currency, ordinal, label), {}).get("source_principal", Decimal(0))
                ),
            }
            for currency in native_currencies
            for ordinal, label in canonical_labels
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
                "status": (
                    "RECONCILED_SOURCE_CURRENCY"
                    if currency in {"CRC", "USD"}
                    else "BLOCKED_NATIVE_CURRENCY"
                ),
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
            "No FX conversion. DOLAR is explicitly mapped to USD by rule "
            "INV-MASTER-CURRENCY-ALIASES-V1 with original source spelling preserved; "
            "unsupported or missing source codes remain excluded. "
            "All nineteen empty or occupied bands are shown for each supported source currency. "
            "Source-column principal only; other balance fields are not substituted. "
            "The cutoff comes from the filename and is not independently certified."
        ),
    }
