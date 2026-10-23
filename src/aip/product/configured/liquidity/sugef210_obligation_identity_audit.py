"""Identity-only reconciliation of CONFÍA obligation maturity bands.

This module never books cash: a range code and an outstanding principal balance
are not a dated, approved settlement. No counterparty IDs, operations, account
numbers, currency amounts or private paths leave the diagnostic.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader

_JOIN_FIELDS = ("IdAcreedor", "IdOperacion")
_CONTRACT_SOURCES = ("CAPTACIONES", "BORROWING")
_MATURITY_SOURCE = "BORROWING_MATURITY"


def _identity(values: dict[str, str]) -> tuple[str, str] | None:
    parts = tuple((values.get(name) or "").strip() for name in _JOIN_FIELDS)
    return (parts[0], parts[1]) if all(parts) else None


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

    contract_index: dict[tuple[str, str], tuple[str, str, str] | None] = {}
    candidates = Counter()
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
            )
            candidates[source_key] += 1
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
    maturity_observed_tags: set[str] = set()
    for record in reader.iter_records(maturity):
        maturity_rows += 1
        maturity_observed_tags.update(record.values)
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
