"""Approved, source-dated investment coupons; never derive interest from yield.

A custodian/Treasury payment ledger is evidence, not a source of invented coupons.
Every coupon must reconcile with an unchanged real Master position, independent
custodian-document hash and individually approved native-currency cash receipt.
No coupon schedule, amount or settlement date is inferred from interest rates.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    MasterPrincipalEvidence,
)

_HEADERS = (
    "master_principal_reference",
    "payment_reference",
    "payment_date",
    "currency",
    "amount",
    "settlement_reference",
    "nonduplication_reference",
)
_MAX_LEDGER = 20 * 1024 * 1024
_MAX_AUTHORIZATION = 2 * 1024 * 1024
_MAX_CUSTODY = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ApprovedMasterCouponSchedule:
    cutoff: date
    events: tuple[LiquidityProjectionFlow, ...]
    master_sha256: str
    ledger_sha256: str
    custodian_sha256: str
    nonduplication_references: frozenset[str]
    status: str = "SELECTED_MASTER_COUPONS_ONLY_NOT_COMPLETE_INVESTMENT_COVERAGE"


def _required(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing investment coupon evidence: " + key)
    return value.strip()


def _amount(value: Any) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Investment coupon amount must be an original decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid original coupon amount") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("Investment coupon must be finite and strictly positive")
    return number


def _date(value: Any, key: str) -> date:
    try:
        return date.fromisoformat(_required(value, key))
    except ValueError as exc:
        raise ValueError("Invalid investment coupon ISO date: " + key) from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in values:
        if key in record:
            raise ValueError("Duplicate investment coupon approval JSON field")
        record[key] = value
    return record


def _check_document(path: Path, expected: str, *, max_bytes: int, name: str) -> str:
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("Missing, empty or oversized " + name)
    expected = _required(expected, name + " hash").lower()
    if len(expected) != 64 or any(x not in "0123456789abcdef" for x in expected):
        raise ValueError("Invalid " + name + " SHA-256")
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(name + " SHA-256 differs from authorization")
    return actual


def read_approved_master_coupons(
    *,
    source: MasterPrincipalEvidence,
    cutoff: date,
    master_sha256: str,
    ledger_file: str | Path,
    approval_file: str | Path,
    custodian_document_file: str | Path,
    prohibited_nonduplication_refs: frozenset[str] = frozenset(),
) -> ApprovedMasterCouponSchedule:
    """Admit only custody-evidenced coupons matched to individually listed Master rows."""
    ledger_path = Path(ledger_file)
    approval_path = Path(approval_file)
    custody_path = Path(custodian_document_file)
    paths = (ledger_path, approval_path, custody_path)
    if any(not path.is_absolute() for path in paths):
        raise ValueError("Coupon evidence requires absolute local institutional paths")
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("Custody document, coupon ledger and approval must be independent")
    if source.cutoff != cutoff or source.master_sha256 != master_sha256:
        raise ValueError("Coupon approval differs from source Master cutoff or hash")
    if source.positions_read != len(source.flows) + len(source.excluded):
        raise ValueError("Original investment Master rows do not reconcile")
    if not approval_path.is_file() or not 0 < approval_path.stat().st_size <= _MAX_AUTHORIZATION:
        raise ValueError("Coupon authorization missing or oversized")
    try:
        authorization = json.loads(
            approval_path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid investment coupon authorization JSON") from exc
    if not isinstance(authorization, dict):
        raise ValueError("Coupon authorization must be a JSON object")
    if _required(authorization.get("schema"), "schema") != "SUGEF210_MASTER_COUPONS_V1":
        raise ValueError("Unsupported investment coupon authorization schema")
    if _date(authorization.get("cutoff"), "cutoff") != cutoff:
        raise ValueError("Investment coupon approval has another cutoff")
    if _required(authorization.get("master_sha256"), "master_sha256").lower() != master_sha256:
        raise ValueError("Investment coupon approval has another Master hash")
    _required(authorization.get("custodian_approval_reference"), "custodian_approval_reference")
    _required(authorization.get("treasury_settlement_approval"), "treasury_settlement_approval")
    _required(authorization.get("nonduplication_approval"), "nonduplication_approval")
    ledger_hash = _check_document(
        ledger_path,
        _required(authorization.get("ledger_sha256"), "ledger_sha256"),
        max_bytes=_MAX_LEDGER,
        name="Coupon ledger",
    )
    custody_hash = _check_document(
        custody_path,
        _required(authorization.get("custodian_document_sha256"), "custodian_document_sha256"),
        max_bytes=_MAX_CUSTODY,
        name="Custodian supporting document",
    )

    approvals = authorization.get("approved_payment_records")
    if not isinstance(approvals, list) or not approvals:
        raise ValueError("Individual dated coupon approvals are mandatory")
    approved_by_ref: dict[str, dict[str, Any]] = {}
    for row in approvals:
        if not isinstance(row, dict):
            raise ValueError("Coupon approved payment record must be structured")
        reference = _required(row.get("payment_reference"), "payment_reference")
        if reference in approved_by_ref:
            raise ValueError("Repeated individual coupon approval")
        if row.get("explicitly_approved") is not True:
            raise ValueError("Unapproved investment coupon cannot be recognized")
        approved_by_ref[reference] = row

    by_master = {item.reference: item for item in source.flows}
    if len(by_master) != len(source.flows):
        raise ValueError("Original Master contains duplicate investment references")
    used_reconciliations: set[str] = set()
    encountered: set[str] = set()
    seen_instrument_dates: set[tuple[str, date]] = set()
    events: list[LiquidityProjectionFlow] = []
    try:
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(_HEADERS):
                raise ValueError("Investment coupon ledger headings do not match approved schema")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Malformed investment coupon payment row")
                reference = _required(row["payment_reference"], "payment_reference")
                if reference in encountered:
                    raise ValueError("Duplicate investment coupon payment reference")
                encountered.add(reference)
                approved = approved_by_ref.get(reference)
                if approved is None:
                    raise ValueError("Coupon ledger payment has no individual approval")
                origin = _required(row["master_principal_reference"], "master_principal_reference")
                master = by_master.get(origin)
                if master is None:
                    raise ValueError("Coupon source row not validated in original Master")
                currency = _required(row["currency"], "currency")
                if currency != master.currency:
                    raise ValueError("Coupon native currency differs from original Master")
                when = _date(row["payment_date"], "payment_date")
                if not cutoff < when <= master.payment_date:
                    raise ValueError("Coupon date is outside future Master instrument life")
                instrument_date = (origin, when)
                if instrument_date in seen_instrument_dates:
                    raise ValueError(
                        "Duplicate coupon cash date for the same original investment position"
                    )
                seen_instrument_dates.add(instrument_date)
                amount = _amount(row["amount"])
                reconciliation = _required(
                    row["nonduplication_reference"], "nonduplication_reference"
                )
                settlement = _required(row["settlement_reference"], "settlement_reference")
                if (
                    reconciliation in used_reconciliations
                    or reconciliation in prohibited_nonduplication_refs
                ):
                    raise ValueError("Coupon payment reuses a cashflow reconciliation reference")
                used_reconciliations.add(reconciliation)
                if (
                    _required(approved.get("master_principal_reference"), "approved master row")
                    != origin
                    or _date(approved.get("payment_date"), "approved payment date") != when
                    or _required(approved.get("currency"), "approved currency") != currency
                    or _amount(approved.get("amount")) != amount
                    or _required(approved.get("settlement_reference"), "approved settlement")
                    != settlement
                    or _required(
                        approved.get("nonduplication_reference"), "approved nonduplication"
                    )
                    != reconciliation
                ):
                    raise ValueError("Coupon ledger and individual authorized payment differ")
                events.append(
                    LiquidityProjectionFlow(
                        reference=f"MASTER_COUPON:{master_sha256}:{reference}",
                        source=(
                            f"CUSTODIAN_SHA256:{custody_hash}:LEDGER_SHA256:{ledger_hash}:"
                            f"{origin}:SETTLEMENT:{settlement}:RECON:{reconciliation}"
                        ),
                        currency=currency,
                        payment_date=when,
                        amount=amount,
                        side=LiquidityFlowSide.INFLOW,
                        area=LiquidityBalanceArea.ASSET,
                        evidence=LiquidityEvidence.CONTRACTUAL,
                    )
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("Cannot read institutional coupon ledger") from exc
    if encountered != set(approved_by_ref):
        raise ValueError("Individual coupon approvals do not exactly match custody ledger")
    if _sha256(ledger_path) != ledger_hash or _sha256(custody_path) != custody_hash:
        raise ValueError("Coupon source evidence changed during reconciliation")
    return ApprovedMasterCouponSchedule(
        cutoff=cutoff,
        events=tuple(events),
        master_sha256=master_sha256,
        ledger_sha256=ledger_hash,
        custodian_sha256=custody_hash,
        nonduplication_references=frozenset(used_reconciliations),
    )
