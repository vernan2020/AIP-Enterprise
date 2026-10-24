"""Identity-only reconciliation of CONFÍA obligation maturity bands.

This module never books cash: a range code and an outstanding principal balance
are not a dated, approved settlement. No counterparty IDs, operations, account
numbers, currency amounts or private paths leave the diagnostic.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader

_JOIN_FIELDS = ("IdAcreedor", "IdOperacion")
_CONTRACT_SOURCES = ("CAPTACIONES", "BORROWING")
_MATURITY_SOURCE = "BORROWING_MATURITY"


def _identity(values: dict[str, str]) -> tuple[str, str] | None:
    parts = tuple((values.get(name) or "").strip() for name in _JOIN_FIELDS)
    return (parts[0], parts[1]) if all(parts) else None


def _principal(value: str) -> Decimal | None:
    """Strict native decimal parsing; unsigned principal, no currency conversion."""
    if not value.strip():
        return None
    try:
        principal = Decimal(value.strip())
    except InvalidOperation:
        return None
    return principal if principal.is_finite() and principal >= 0 else None


def _range_code(value: str) -> str:
    """Do not echo unexpected text from a source code in operator diagnostics."""
    raw = value.strip()
    return raw if raw and len(raw) <= 12 and raw.isascii() and raw.isalnum() else "(SIN CÓDIGO)"


def _maturity_category(value: str, cutoff: date) -> str:
    """Inspect the literal date; do not infer contractual tenor or withdrawal."""
    if not value.strip():
        return "SOURCE_MATURITY_BLANK"
    try:
        maturity = datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return "SOURCE_MATURITY_INVALID"
    days = (maturity - cutoff).days
    if days <= 0:
        return "SOURCE_MATURITY_PAST_OR_CUTOFF"
    return "SOURCE_MATURITY_WITHIN_365D" if days <= 365 else "SOURCE_MATURITY_AFTER_365D"


def _principal_problem(value: str) -> str:
    """Only short categories are returned; financial input is never echoed."""
    raw = value.strip()
    if not raw:
        return "BLANK"
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return "NOT_A_DECIMAL"
    if not amount.is_finite():
        return "NONFINITE"
    return "NEGATIVE" if amount < 0 else "VALID"


def _bounded_counts(values: Counter[str], limit: int = 25) -> dict[str, int]:
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    result = dict(ordered[:limit])
    remainder = sum(count for _, count in ordered[limit:])
    if remainder:
        result["(OTHER_CATEGORIES)"] = remainder
    return result


def audit_obligation_maturity_identity(
    *, reader: XMLConfiaMonthlySourceReader, cutoff: date
) -> dict[str, Any]:
    """Read same-cutoff sources and report only aggregate join-quality counts.

    Two different rows claiming the same composite key are ambiguous, even
    when their financial attributes agree. Never match on operation ID alone.
    """
    try:
        maturity = reader.resolve_source(key=_MATURITY_SOURCE, cutoff_date=cutoff)
    except (OSError, ValueError, KeyError) as exc:
        return {
            "status": "BLOCKED_MATURITY_SOURCE_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "cashflows_recognized": 0,
        }

    contract_index: dict[
        tuple[str, str], tuple[str, str, str, Decimal | None, str, str, str] | None
    ] = {}
    contracts_observed: set[str] = set()
    source_details: list[dict[str, Any]] = []
    header_mismatch = False

    for source_key in _CONTRACT_SOURCES:
        try:
            source = reader.resolve_source(key=source_key, cutoff_date=cutoff)
        except (OSError, ValueError, KeyError) as exc:
            source_details.append(
                {
                    "source_key": source_key,
                    "status": "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO",
                    "error_type": type(exc).__name__,
                }
            )
            continue

        header_ok = (
            source.header.id_entidad == maturity.header.id_entidad
            and source.header.periodo == maturity.header.periodo
        )
        header_mismatch |= not header_ok
        records = 0
        missing_identity = 0
        duplicated_records = 0
        observed_tags: set[str] = set()
        for record in reader.iter_records(source):
            records += 1
            observed_tags.update(record.values)
            identity = _identity(record.values)
            if identity is None:
                missing_identity += 1
                continue
            if identity in contract_index:
                duplicated_records += 1
                contract_index[identity] = None
                continue
            contract_index[identity] = (
                source_key,
                (record.values.get("TipoMonedaObligacion") or "").strip(),
                (record.values.get("CuentaContablePrincipal") or "").strip(),
                _principal(record.values.get("SaldoPrincipal") or ""),
                _range_code(record.values.get("TipoCuenta") or ""),
                _maturity_category(record.values.get("FechaVencimiento") or "", cutoff),
                _principal_problem(record.values.get("SaldoPrincipal") or ""),
            )
        contracts_observed.update(observed_tags)
        source_details.append(
            {
                "source_key": source_key,
                "status": "INDEX_INSPECTED_NO_CASHFLOWS",
                "records": records,
                "records_without_composite_identity": missing_identity,
                "duplicate_identity_rows": duplicated_records,
                "required_identity_tags_present": all(
                    name in observed_tags for name in _JOIN_FIELDS
                ),
                "same_entity_and_reporting_period": header_ok,
            }
        )

    maturity_rows = 0
    incomplete = 0
    unique = 0
    ambiguous = 0
    unmatched = 0
    unique_currency = 0
    unique_account = 0
    matched_sources: Counter[str] = Counter()
    distinct_matched: set[tuple[str, str]] = set()
    repeated_maturity_rows = 0
    maturity_sums: dict[tuple[str, str], Decimal] = {}
    invalid_maturity_identities: set[tuple[str, str]] = set()
    maturity_amounts_missing_or_invalid = 0
    range_counts: Counter[str] = Counter()
    maturity_observed_tags: set[str] = set()
    for record in reader.iter_records(maturity):
        maturity_rows += 1
        maturity_observed_tags.update(record.values)
        range_counts[_range_code(record.values.get("TipoRangoPasivo") or "")] += 1
        identity = _identity(record.values)
        if identity is None:
            incomplete += 1
        elif identity not in contract_index:
            unmatched += 1
        else:
            match = contract_index[identity]
            if match is None:
                ambiguous += 1
            else:
                unique += 1
                matched_sources[match[0]] += 1
                unique_currency += bool(match[1])
                unique_account += bool(match[2])
                if identity in distinct_matched:
                    repeated_maturity_rows += 1
                distinct_matched.add(identity)
                principal = _principal(record.values.get("SaldoaPagarPrincipal") or "")
                if principal is None:
                    maturity_amounts_missing_or_invalid += 1
                    invalid_maturity_identities.add(identity)
                else:
                    maturity_sums[identity] = maturity_sums.get(identity, Decimal(0)) + principal

    unbanded_by_source: Counter[str] = Counter()
    exact_principal = 0
    differing_principal = 0
    contract_principal_unusable = 0
    band_principal_unusable = 0
    contracts_with_any_principal_issue = 0
    contract_principal_issue_reasons: Counter[str] = Counter()
    unbanded_type_counts: Counter[str] = Counter()
    unbanded_maturity_categories: Counter[str] = Counter()
    unbanded_currency_counts: Counter[str] = Counter()
    for identity, contract in contract_index.items():
        if contract is None:
            continue
        if identity not in distinct_matched:
            unbanded_by_source[contract[0]] += 1
            unbanded_type_counts[f"{contract[0]}:{contract[4]}"] += 1
            unbanded_maturity_categories[contract[5]] += 1
            unbanded_currency_counts[_range_code(contract[1])] += 1
            continue
        missing_source_principal = contract[3] is None
        missing_band_principal = identity in invalid_maturity_identities
        if missing_source_principal:
            contract_principal_unusable += 1
            contract_principal_issue_reasons[contract[6]] += 1
        if missing_band_principal:
            band_principal_unusable += 1
        if missing_source_principal or missing_band_principal:
            contracts_with_any_principal_issue += 1
        elif maturity_sums[identity] == contract[3]:
            exact_principal += 1
        else:
            differing_principal += 1

    missing_contract_sources = sum(
        row["status"] == "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO" for row in source_details
    )
    if header_mismatch:
        status = "BLOCKED_SOURCE_HEADER_MISMATCH"
    elif missing_contract_sources:
        status = "PARTIAL_SOURCE_COVERAGE"
    elif incomplete == maturity_rows and maturity_rows:
        status = "COMPOSITE_IDENTITY_NOT_AVAILABLE"
    elif ambiguous:
        status = "AMBIGUOUS_LINKAGE_REVIEW"
    elif unique:
        status = "MATCHED_REFERENCE_ONLY"
    else:
        status = "NO_UNIQUE_CONTRACTUAL_LINKAGE"

    return {
        "status": status,
        "cutoff": cutoff.isoformat(),
        "maturity_records": maturity_rows,
        "maturity_identity_tags_present": all(
            name in maturity_observed_tags for name in _JOIN_FIELDS
        ),
        "contract_source_identity_tags_present": all(
            name in contracts_observed for name in _JOIN_FIELDS
        ),
        "candidate_distinct_identities": len(contract_index),
        "unique_maturity_rows_matched": unique,
        "distinct_contracts_with_maturity_bands": len(distinct_matched),
        "matched_maturity_rows_on_repeated_contracts": repeated_maturity_rows,
        "contract_identities_without_maturity_bands_by_source": dict(
            sorted(unbanded_by_source.items())
        ),
        "unbanded_contracts_by_original_type_code": _bounded_counts(
            unbanded_type_counts
        ),
        "unbanded_contracts_by_native_currency_code": _bounded_counts(
            unbanded_currency_counts
        ),
        "unbanded_contracts_by_original_maturity_state": dict(
            sorted(unbanded_maturity_categories.items())
        ),
        "range_code_record_counts": dict(sorted(range_counts.items())),
        "maturity_principal_values_missing_or_invalid": maturity_amounts_missing_or_invalid,
        "principal_reconciliation": {
            "status": "COUNTED_NOT_CERTIFIED",
            "distinct_contracts_reconciled_exactly": exact_principal,
            "distinct_contracts_with_principal_difference": differing_principal,
            "matched_contracts_without_usable_source_principal": contract_principal_unusable,
            "matched_contracts_without_usable_band_principal": band_principal_unusable,
            "distinct_contracts_with_invalid_principal_on_either_side": (
                contracts_with_any_principal_issue
            ),
            "source_principal_issue_causes": dict(
                sorted(contract_principal_issue_reasons.items())
            ),
            "monetary_tolerance_applied": False,
            "sensitive_amounts_disclosed": False,
            "cashflow_payments_approved": 0,
        },
        "identity_match_coverage_complete": unique == maturity_rows and maturity_rows > 0,
        "ambiguous_maturity_rows": ambiguous,
        "unmatched_maturity_rows": unmatched,
        "maturity_rows_without_composite_identity": incomplete,
        "unique_matches_with_original_currency_code": unique_currency,
        "unique_matches_with_original_account_code": unique_account,
        "matched_contract_source_counts": dict(sorted(matched_sources.items())),
        "contract_sources": source_details,
        "currency_approved_for_projection": False,
        "range_codes_mapped_to_dates": False,
        "payment_schedule_certified": False,
        "cashflows_recognized": 0,
    }
