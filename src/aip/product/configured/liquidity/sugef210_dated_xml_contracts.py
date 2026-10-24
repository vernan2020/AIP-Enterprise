"""Read source-dated, independently approved payments against native CONFIA XML.

No XML balance or regulatory maturity band is a dated cashflow. Only a separately
supplied approved, hashed payment ledger with one-to-one XML source lineage and
full principal reconciliation can contribute individual cashflow events.
Partial records never attest coverage for a whole financial statement perimeter.
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader

_REQUIRED = (
    "source_key",
    "source_ordinal",
    "source_record_id",
    "account_code",
    "original_currency_code",
    "currency",
    "original_principal",
    "maturity_date",
    "payment_reference",
    "payment_date",
    "flow_type",
    "amount",
    "availability_reference",
)
_SUPPORTED = frozenset({"CREDIT", "CAPTACIONES", "BORROWING"})
_PRINCIPAL_FIELDS = {
    "CREDIT": ("SaldoPrincipalOperacionCrediticia", "TipoMonedaOperacion"),
    "CAPTACIONES": ("SaldoPrincipal", "TipoMonedaObligacion"),
    "BORROWING": ("SaldoPrincipal", "TipoMonedaObligacion"),
}
_MAX_CSV_SIZE = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ApprovedXMLContractualSchedule:
    cutoff: date
    events: tuple[LiquidityProjectionFlow, ...]
    source_hashes: tuple[tuple[str, str], ...]
    ledger_sha256: str
    included_source_records: tuple[tuple[str, int], ...]
    status: str = "SELECTED_SOURCE_DATED_PAYMENTS_NOT_COMPLETE_PERIMETER"

    @property
    def certifies_entire_perimeter(self) -> bool:
        return False


def _require(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing contractual source field: {name}")
    return value.strip()


def _amount(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid native contractual amount") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("Dated contractual amounts must be positive and finite")
    return result


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Dated contractual payments require ISO dates") from exc


def _xml_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError("Original XML maturity date is missing or invalid") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while data := source.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def import_approved_xml_contractual_payments(
    *,
    reader: XMLConfiaMonthlySourceReader,
    cutoff: date,
    ledger_file: str | Path,
    expected_ledger_sha256: str,
    approved_xml_sha256: dict[str, str],
    approved_currency_codes: dict[str, str],
    approved_term_deposit_codes: frozenset[str] = frozenset(),
    source_payment_approval: str,
    settlement_approval: str,
    nonduplication_reference: str,
    already_booked_references: frozenset[str] = frozenset(),
) -> ApprovedXMLContractualSchedule:
    """Admit selected source payments; record lineage and native amount must agree.

    The CSV is a separate contractual amortization/coupon schedule. Every selected
    record's entire outstanding principal must reconcile, including dates beyond
    day 365. Credit balances cannot be ballooned to maturity; demand deposits
    lacking a fixed original maturity are rejected.
    """
    if not all(
        text.strip()
        for text in (source_payment_approval, settlement_approval, nonduplication_reference)
    ):
        raise ValueError("Separate payment, settlement and nonduplication approvals required")
    path = Path(ledger_file)
    if not path.is_file() or path.stat().st_size > _MAX_CSV_SIZE:
        raise ValueError("Approved contractual ledger missing or oversized")
    ledger_hash = _sha256(path)
    if ledger_hash != expected_ledger_sha256.lower() or len(expected_ledger_sha256) != 64:
        raise ValueError("Contractual ledger changed after approval")
    if not approved_xml_sha256 or any(
        key not in _SUPPORTED or len(value) != 64 for key, value in approved_xml_sha256.items()
    ):
        raise ValueError("Explicit XML source hashes are required for selected perimeters")
    if not approved_currency_codes or any(
        not code or currency not in {"CRC", "USD"}
        for code, currency in approved_currency_codes.items()
    ):
        raise ValueError("Explicit original XML currency mapping is required")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        input_reader = csv.DictReader(file)
        if (
            input_reader.fieldnames is None
            or len(input_reader.fieldnames) != len(set(input_reader.fieldnames))
            or set(input_reader.fieldnames) != set(_REQUIRED)
        ):
            raise ValueError("Source payment CSV must have exact unique governed columns")
        rows = list(input_reader)
    if not rows:
        raise ValueError("No real contractual payment records were supplied")
    if len(rows) > 250000:
        raise ValueError("Contractual payment ledger exceeds approved size")

    if approved_term_deposit_codes and any(
        not item.strip() for item in approved_term_deposit_codes
    ):
        raise ValueError("Blank approved term-deposit source classification")
    by_key: dict[str, tuple[dict[int, Any], str]] = {}
    selected_sources = {_require(row.get("source_key"), "source_key") for row in rows}
    if not selected_sources.issubset(_SUPPORTED) or selected_sources != set(approved_xml_sha256):
        raise ValueError("Selected XML contractual sources and approved hashes disagree")
    source_entity_ids: set[str] = set()
    for key in sorted(selected_sources):
        original = reader.resolve_source(key=key, cutoff_date=cutoff)
        if (original.header.periodo.year, original.header.periodo.month) != (
            cutoff.year,
            cutoff.month,
        ) or not original.header.id_entidad.strip():
            raise ValueError("Original source entity and requested reporting month mismatch")
        source_entity_ids.add(original.header.id_entidad)
        if len(source_entity_ids) != 1:
            raise ValueError("Contractual sources belong to different reporting entities")
        actual_hash = reader.sha256(original.path)
        if actual_hash != approved_xml_sha256[key].lower():
            raise ValueError("Original CONFIA XML source hash changed after approval")
        indexed: dict[int, Any] = {}
        raw_ids: set[str] = set()
        for ordinal, item in enumerate(reader.iter_records(original), 1):
            if not item.record_id.strip() or item.record_id in raw_ids:
                raise ValueError("Original contractual XML contains ambiguous record IDs")
            raw_ids.add(item.record_id)
            indexed[ordinal] = item
        by_key[key] = indexed, actual_hash

    payments: list[LiquidityProjectionFlow] = []
    observed_payments: set[str] = set()
    contract_principal: dict[tuple[str, int], Decimal] = defaultdict(Decimal)
    contract_details: dict[tuple[str, int], tuple[Decimal, date, str]] = {}
    for row in rows:
        key = _require(row.get("source_key"), "source_key")
        raw_ordinal = _require(row.get("source_ordinal"), "source_ordinal")
        if not raw_ordinal.isdigit() or int(raw_ordinal) <= 0:
            raise ValueError("Original XML row ordinal must be positive")
        ordinal = int(raw_ordinal)
        original = by_key[key][0].get(ordinal)
        if original is None:
            raise ValueError("Contractual payment row not present in original CONFIA XML")
        if _require(row.get("source_record_id"), "source_record_id") != original.record_id:
            raise ValueError("Contractual record identity differs from original CONFIA XML")
        values = original.values
        if key == "CAPTACIONES" and (
            not approved_term_deposit_codes
            or (values.get("TipoCuenta") or "").strip() not in approved_term_deposit_codes
        ):
            raise ValueError("Demand deposits cannot be converted into term maturities")
        source_balance_field, source_currency_field = _PRINCIPAL_FIELDS[key]
        native_currency_code = _require(row.get("original_currency_code"), "original_currency_code")
        currency = _require(row.get("currency"), "currency")
        if (
            _require(row.get("account_code"), "account_code")
            != (values.get("CuentaContablePrincipal") or "").strip()
            or native_currency_code != (values.get(source_currency_field) or "").strip()
            or approved_currency_codes.get(native_currency_code) != currency
        ):
            raise ValueError("Contractual account or native currency does not match XML")
        principal = _amount(_require(row.get("original_principal"), "original_principal"))
        if principal != _amount((values.get(source_balance_field) or "").strip()):
            raise ValueError("Contractual original principal disagrees with XML source")
        maturity = _xml_date((values.get("FechaVencimiento") or "").strip())
        if _date(_require(row.get("maturity_date"), "maturity_date")) != maturity:
            raise ValueError("Contractual maturity differs from original XML source")
        if maturity <= cutoff:
            raise ValueError("Matured contractual source cannot generate future cash")
        payment_date = _date(_require(row.get("payment_date"), "payment_date"))
        if payment_date <= cutoff or payment_date > maturity:
            raise ValueError("Payment date is historical or after contractual maturity")
        if not _require(row.get("availability_reference"), "availability_reference"):
            raise ValueError("Original payment availability evidence required")
        kind = _require(row.get("flow_type"), "flow_type").upper()
        if kind not in {"PRINCIPAL", "INTEREST"}:
            raise ValueError("Only separately dated principal or interest admitted")
        record_key = key, ordinal
        details = principal, maturity, currency
        if record_key in contract_details and contract_details[record_key] != details:
            raise ValueError("Conflicting source principal, maturity or currency")
        contract_details[record_key] = details
        if kind == "PRINCIPAL":
            contract_principal[record_key] += _amount(_require(row.get("amount"), "amount"))
        payment_reference = _require(row.get("payment_reference"), "payment_reference")
        identifier = f"XML_CONTRACT:{key}:{by_key[key][1]}:{ordinal}:{payment_reference}"
        if identifier in observed_payments or identifier in already_booked_references:
            raise ValueError("Duplicated contractual event or existing cash opening")
        observed_payments.add(identifier)
        area = LiquidityBalanceArea.ASSET if key == "CREDIT" else LiquidityBalanceArea.LIABILITY
        payments.append(
            LiquidityProjectionFlow(
                reference=identifier,
                source=(
                    f"APPROVED_XML_LEDGER:{ledger_hash}:{source_payment_approval}:"
                    f"{settlement_approval}:{nonduplication_reference}"
                ),
                currency=currency,
                payment_date=payment_date,
                amount=_amount(_require(row.get("amount"), "amount")),
                side=LiquidityFlowSide.INFLOW if key == "CREDIT" else LiquidityFlowSide.OUTFLOW,
                area=area,
                evidence=LiquidityEvidence.CONTRACTUAL,
            )
        )
    for record_identity, (original_principal, _maturity, _currency) in contract_details.items():
        if contract_principal[record_identity] != original_principal:
            raise ValueError("Scheduled principal does not reconcile to original XML exposure")
    return ApprovedXMLContractualSchedule(
        cutoff=cutoff,
        events=tuple(payments),
        source_hashes=tuple(sorted((key, info[1]) for key, info in by_key.items())),
        ledger_sha256=ledger_hash,
        included_source_records=tuple(sorted(contract_details)),
    )



def merge_approved_xml_contractual_schedules(
    *, cutoff: date, schedules: Iterable[ApprovedXMLContractualSchedule]
) -> ApprovedXMLContractualSchedule:
    """Merge independently attested CSV partitions without counting a contract twice.

    Each partition must reconcile a contract's entire outstanding principal
    independently; splitting installments for one contract across CSVs is
    deliberately rejected. Each file retains its own source SHA and approval.
    """
    partitions = tuple(schedules)
    if not partitions or len(partitions) > 32:
        raise ValueError("One to 32 independently approved payment partitions required")
    source_hashes: dict[str, str] = {}
    seen_files: set[str] = set()
    seen_records: set[tuple[str, int]] = set()
    seen_events: set[str] = set()
    events: list[LiquidityProjectionFlow] = []
    for item in partitions:
        if item.cutoff != cutoff or item.status != (
            "SELECTED_SOURCE_DATED_PAYMENTS_NOT_COMPLETE_PERIMETER"
        ):
            raise ValueError("Contractual payment partitions have conflicting cutoffs or status")
        if len(item.ledger_sha256) != 64 or item.ledger_sha256 in seen_files:
            raise ValueError("Contractual payment CSV partition is repeated")
        seen_files.add(item.ledger_sha256)
        for key, digest in item.source_hashes:
            if key in source_hashes and source_hashes[key] != digest:
                raise ValueError("Conflicting source hashes across contractual partitions")
            source_hashes[key] = digest
        for record in item.included_source_records:
            if record in seen_records:
                raise ValueError("Contractual operation repeats across approved partitions")
            seen_records.add(record)
        for event in item.events:
            if event.reference in seen_events:
                raise ValueError("Contractual cash event repeats across approved partitions")
            seen_events.add(event.reference)
            events.append(event)
    if not events or not seen_records or not source_hashes:
        raise ValueError("Approved payment partitions must contain dated source events")
    combined_hash = hashlib.sha256(
        "\n".join(sorted(seen_files)).encode("ascii")
    ).hexdigest()
    return ApprovedXMLContractualSchedule(
        cutoff=cutoff,
        events=tuple(events),
        source_hashes=tuple(sorted(source_hashes.items())),
        ledger_sha256=combined_hash,
        included_source_records=tuple(sorted(seen_records)),
    )
