"""Nineteen-band observed maturity evidence for fixed-term Captaciones XML.

This audit reports the source principal against its *reported* maturity date.
It is NOT the contractual payment schedule, repricing GAP, EVE or NII.
Only fixed-rate term-account families with valid future XML maturities qualify.
NMD, matured, variable-rate and unverified entries remain explicit exclusions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
from aip.product.configured.irrbb.captaciones_irrbb_account_classifier import (
    CaptacionesIRRBBAccountClassifier,
)
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaMonthlySourceReader,
)

SOURCE_KEY = "CAPTACIONES"
EVIDENCE_ONLY = "MATURITY_EVIDENCE_ONLY_NOT_IRRBB_GAP"


class _SourceReader(Protocol):
    def resolve_source(self, *, key: str, cutoff_date: date): ...

    def iter_records(self, source): ...


@dataclass
class _BandBalance:
    records: int = 0
    balance: Decimal = Decimal(0)


def _valid_principal(value: str) -> Decimal | None:
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


def _source_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def _account_status(account: str) -> str:
    governed = CaptacionesIRRBBAccountClassifier
    if not account.isdigit():
        return "UNSUPPORTED_ACCOUNT"
    if account.startswith(governed._SIGHT_PREFIXES):
        return "SIGHT_NMD_BEHAVIORAL_PROFILE_REQUIRED"
    if account.startswith(governed._MATURED_TERM_PREFIXES):
        return "MATURED_TERM_POLICY_REQUIRED"
    if account.startswith(governed._TERM_PREFIXES):
        return "TERM"
    return "UNSUPPORTED_ACCOUNT"


def inspect_fixed_term_maturities(
    reader: XMLConfiaMonthlySourceReader,
    cutoff: date,
) -> dict[str, object]:
    """Preserve every XML record as either one band or one documented exclusion."""
    source = reader.resolve_source(key=SOURCE_KEY, cutoff_date=cutoff)
    if (source.header.periodo.year, source.header.periodo.month) != (
        cutoff.year,
        cutoff.month,
    ):
        raise ValueError("Captaciones XML reporting month differs from requested cutoff")

    bands: dict[tuple[str, int, str], _BandBalance] = {}
    excluded_counts: dict[tuple[str, str], int] = {}
    excluded_principal: dict[tuple[str, str], Decimal] = {}
    term_rate_review: dict[tuple[str, str, str], _BandBalance] = {}
    source_valid_principal: dict[str, Decimal] = {}
    source_invalid_principal_records: dict[str, int] = {}
    seen_ids: set[str] = set()
    total_records = 0

    for record in reader.iter_records(source):
        total_records += 1
        if not record.record_id or record.record_id in seen_ids:
            raise ValueError("Captaciones XML record identifiers must be unique and nonempty")
        seen_ids.add(record.record_id)
        values = record.values
        currency = values.get("TipoMonedaObligacion", "").strip() or "(VACIO)"
        amount = _valid_principal(values.get("SaldoPrincipal", "").strip())
        if amount is not None:
            source_valid_principal[currency] = (
                source_valid_principal.get(currency, Decimal(0)) + amount
            )
        else:
            source_invalid_principal_records[currency] = (
                source_invalid_principal_records.get(currency, 0) + 1
            )

        status = _account_status(values.get("CuentaContablePrincipal", "").strip())
        if status == "TERM":
            raw_rate = values.get("TipoTasa", "").strip().upper() or "(VACIO)"
            raw_maturity = values.get("FechaVencimiento", "").strip()
            parsed_maturity = _source_date(raw_maturity) if raw_maturity else None
            if not raw_maturity:
                date_quality = "MISSING_MATURITY"
            elif parsed_maturity is None:
                date_quality = "INVALID_MATURITY"
            elif parsed_maturity < cutoff:
                date_quality = "PAST_MATURITY"
            else:
                date_quality = "CURRENT_OR_FUTURE_MATURITY"
            review = term_rate_review.setdefault(
                (currency, raw_rate, date_quality), _BandBalance()
            )
            review.records += 1
            if amount is not None:
                review.balance += amount
        if currency == "(VACIO)":
            status = "MISSING_CURRENCY"
        elif amount is None:
            status = "INVALID_PRINCIPAL"
        elif status == "TERM":
            if values.get("TipoTasa", "").strip().upper() != "F":
                status = "TERM_NOT_FIXED_REPRICING_REQUIRED"
            elif not values.get("FechaVencimiento", "").strip():
                status = "TERM_MISSING_MATURITY"
            else:
                maturity = _source_date(values["FechaVencimiento"].strip())
                if maturity is None:
                    status = "TERM_INVALID_MATURITY"
                elif maturity < cutoff:
                    status = "TERM_PAST_MATURITY"
                else:
                    assignment = IRRBBTimeBucketService.assign(
                        valuation_date=cutoff,
                        risk_date=maturity,
                    )
                    key = (currency, assignment.ordinal, assignment.label)
                    current = bands.setdefault(key, _BandBalance())
                    current.records += 1
                    current.balance += amount
                    continue

        key_excluded = (currency, status)
        excluded_counts[key_excluded] = excluded_counts.get(key_excluded, 0) + 1
        if amount is not None:
            excluded_principal[key_excluded] = (
                excluded_principal.get(key_excluded, Decimal(0)) + amount
            )

    observed = sum(row.records for row in bands.values())
    excluded = sum(excluded_counts.values())
    if total_records != observed + excluded:
        raise ValueError("Captaciones maturity audit did not reconcile source record count")
    bucketed_by_currency: dict[str, Decimal] = {}
    for (currency, _ordinal, _label), group in bands.items():
        bucketed_by_currency[currency] = (
            bucketed_by_currency.get(currency, Decimal(0)) + group.balance
        )
    excluded_by_currency: dict[str, Decimal] = {}
    for (currency, _reason), amount in excluded_principal.items():
        excluded_by_currency[currency] = excluded_by_currency.get(currency, Decimal(0)) + amount
    for currency, source_amount in source_valid_principal.items():
        if (
            bucketed_by_currency.get(currency, Decimal(0))
            + excluded_by_currency.get(currency, Decimal(0))
            != source_amount
        ):
            raise ValueError("Captaciones principal does not reconcile by XML currency")
    return {
        "status": EVIDENCE_ONLY,
        "cutoff": cutoff.isoformat(),
        "filename": source.path.name,
        "source_records": total_records,
        "observed_records": observed,
        "excluded_records": excluded,
        "currency_reconciliation": [
            {
                "currency_code": currency,
                "source_valid_principal": str(source_amount),
                "assigned_principal": str(bucketed_by_currency.get(currency, Decimal(0))),
                "excluded_valid_principal": str(excluded_by_currency.get(currency, Decimal(0))),
                "invalid_principal_records": source_invalid_principal_records.get(currency, 0),
                "difference": "0",
                "status": (
                    "PARTIAL_INVALID_PRINCIPAL"
                    if source_invalid_principal_records.get(currency, 0)
                    else "RECONCILED_VALID_PRINCIPAL"
                ),
            }
            for currency in sorted(
                set(source_valid_principal) | set(source_invalid_principal_records)
            )
            for source_amount in (source_valid_principal.get(currency, Decimal(0)),)
        ],
        "bands": [
            {
                "currency_code": currency,
                "ordinal": ordinal,
                "band": label,
                "records": amount.records,
                "source_principal": str(amount.balance),
            }
            for (currency, ordinal, label), amount in sorted(
                bands.items(), key=lambda item: (item[0][0], item[0][1])
            )
        ],
        "term_rate_review": [
            {
                "currency_code": currency,
                "rate_type_source_code": rate_code,
                "maturity_quality": date_quality,
                "records": group.records,
                "valid_source_principal": str(group.balance),
            }
            for (currency, rate_code, date_quality), group in sorted(
                term_rate_review.items()
            )
        ],
        "excluded": [
            {
                "currency_code": currency,
                "reason": reason,
                "records": excluded_counts[(currency, reason)],
                "source_principal": str(excluded_principal.get((currency, reason), Decimal(0))),
            }
            for currency, reason in sorted(excluded_counts)
        ],
        "note": (
            "Source-reported maturity of fixed-rate term deposits only. "
            "Not joined to CAPF contractual certificate schedules; not repricing, "
            "amortization, 19-band certified GAP, Delta EVE or Delta NII. "
            "Unconverted XML currency codes."
        ),
    }
