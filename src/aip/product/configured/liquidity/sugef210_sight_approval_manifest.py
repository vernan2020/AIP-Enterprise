"""Load signed-off sight investment records against an already-inspected XML audit.

This is an institutional approval intake, not a way to manufacture cash. The
opening balance is supplied independently by treasury/ICL; neither principal
balances nor unsigned records are promoted to opening liquidity.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentXMLCurrentAccountAudit,
)
from aip.product.configured.liquidity.sight_investment_opening_bridge import (
    SightOpeningLiquidityResult,
    VerifiedSightInvestmentBalance,
    add_verified_sight_investments_to_opening,
)


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Duplicated approval manifest JSON key")
        values[key] = value
    return values


def _text(row: dict[str, Any], key: str) -> str:
    item = row.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError("Missing institutional sight-approval field: " + key)
    return item.strip()


def _decimal(row: dict[str, Any], key: str) -> Decimal:
    original = _text(row, key)
    try:
        amount = Decimal(original)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal in sight approval: " + key) from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Sight approval amount must be finite and nonnegative")
    return amount


def _iso_date(row: dict[str, Any], key: str) -> date:
    raw = _text(row, key)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Invalid ISO date in sight approval: " + key) from exc


def read_approved_sight_manifest(
    *,
    manifest_path: str | Path,
    cutoff: date,
    source_audit: InvestmentXMLCurrentAccountAudit,
    bank_reconciled_opening: dict[str, Decimal],
    opening_certifications: dict[str, str],
    already_in_opening: frozenset[str] = frozenset(),
) -> SightOpeningLiquidityResult:
    """Validate original XML amount, account, currency, bank opening and approvals.

    Callers MUST obtain source_audit from actual current-month CONFIA XML using
    Institutionally approved accounting account codes. Never accept a synthetic
    audit or guessed source-currency conversion as operational evidence.
    """
    location = Path(manifest_path)
    if not location.is_file() or location.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Sight approval manifest is unavailable or oversized")
    try:
        document = json.loads(
            location.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Sight approval manifest cannot be read safely") from exc
    if not isinstance(document, dict):
        raise ValueError("Sight approval manifest must be a JSON object")
    if _text(document, "schema") != "SUGEF210_SIGHT_OPENING_V1":
        raise ValueError("Sight approval manifest schema is unsupported")
    if _iso_date(document, "cutoff") != cutoff or source_audit.cutoff != cutoff:
        raise ValueError("XML, manifest and bank opening cutoff differ")
    if _text(document, "xml_sha256") != source_audit.xml_sha256:
        raise ValueError("Sight approval no longer matches current source XML hash")
    if not source_audit.records or source_audit.repeated_record_ids:
        raise ValueError("Real XML source audit missing or contains repeated records")
    classification_reference = _text(document, "account_classification_approval")
    mapping_approval = _text(document, "currency_mapping_approval_reference")
    reconciliation = _text(document, "opening_reconciliation_reference")
    if not opening_certifications or any(
        not isinstance(opening_certifications.get(currency), str)
        or not opening_certifications[currency].strip()
        for currency in bank_reconciled_opening
    ):
        raise ValueError("Independent currency-specific bank opening certification required")
    if any(currency not in {"CRC", "USD"} for currency in bank_reconciled_opening):
        raise ValueError("Unrecognized bank opening currency")
    account_codes = document.get("approved_account_codes")
    mapping = document.get("approved_currency_mapping")
    rows = document.get("approved_records")
    if (
        not isinstance(account_codes, list)
        or not account_codes
        or any(not isinstance(code, str) or not code.strip() for code in account_codes)
        or not isinstance(mapping, dict)
        or not mapping
        or any(
            not isinstance(code, str) or not code.strip() or currency not in {"CRC", "USD"}
            for code, currency in mapping.items()
        )
        or not isinstance(rows, list)
        or not rows
        or len(rows) > source_audit.records_read
    ):
        raise ValueError("Sight approval manifest mapping or records are incomplete")
    if len(set(account_codes)) != len(account_codes):
        raise ValueError("Repeated approved current account classification")
    verified = []
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Sight approval records must be JSON objects")
        account = _text(item, "accounting_account")
        if account not in account_codes:
            raise ValueError("XML account not included in approved current account catalog")
        verified.append(
            VerifiedSightInvestmentBalance(
                source_record_reference=_text(item, "source_record_reference"),
                xml_sha256=source_audit.xml_sha256,
                cutoff=cutoff,
                accounting_account=account,
                currency=_text(item, "currency"),
                xml_principal=_decimal(item, "xml_principal"),
                confirmed_available=_decimal(item, "confirmed_available"),
                withdrawal_available_date=_iso_date(item, "withdrawal_available_date"),
                account_classification_approval=classification_reference,
                operational_availability_evidence=_text(item, "availability_evidence"),
                nonduplication_reconciliation=_text(item, "nonduplication_reconciliation"),
                restriction_clearance_reference=_text(item, "restriction_clearance_reference"),
            )
        )
    if len(set(row.source_record_reference for row in verified)) != len(verified):
        raise ValueError("Repeated source record in sight approval manifest")
    return add_verified_sight_investments_to_opening(
        cutoff=cutoff,
        existing_opening=bank_reconciled_opening,
        source_accounts=verified,
        source_audit=source_audit,
        approved_currency_mapping=mapping,
        currency_mapping_approval_reference=mapping_approval,
        opening_reconciliation_reference=reconciliation,
        existing_source_references=already_in_opening,
    )
