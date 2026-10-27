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
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaMonthlySourceReader,
    XMLConfiaRecord,
)

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
    source_entity_id: str | None = None
    source_record_counts: tuple[tuple[str, int], ...] = ()

    @property
    def certifies_entire_perimeter(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class VerifiedContractualXMLSource:
    """One verified on-disk source, scoped to a single opening-session invocation."""

    path: Path
    sha256: str
    entity_id: str
    selected_ordinals: frozenset[int]
    total_records: int
    indexed_rows: dict[int, XMLConfiaRecord]


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


def select_approved_partition_source_ordinals(
    ledgers: Iterable[tuple[Path, str]],
) -> dict[str, frozenset[int]]:
    """Select only XML rows referenced by signed ledgers before parsing large sources.

    This is a preflight index, NOT an approval and NOT a cashflow. Each ledger
    and XML are independently reverified during actual payment admission.
    """
    selected: dict[str, set[int]] = defaultdict(set)
    for path, expected_hash in ledgers:
        if not path.is_file() or path.stat().st_size > _MAX_CSV_SIZE:
            raise ValueError("Contractual payment ledger missing or oversized")
        if len(expected_hash) != 64 or _sha256(path) != expected_hash.lower():
            raise ValueError("Contractual ledger changed after approval")
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if (
                reader.fieldnames is None
                or len(reader.fieldnames) != len(set(reader.fieldnames))
                or set(reader.fieldnames) != set(_REQUIRED)
            ):
                raise ValueError("Source payment CSV must have exact unique governed columns")
            count = 0
            for row in reader:
                count += 1
                if count > 250000:
                    raise ValueError("Contractual payment ledger exceeds approved size")
                source_key = _require(row.get("source_key"), "source_key")
                if source_key not in _SUPPORTED:
                    raise ValueError("Unsupported original contractual source")
                original_ordinal = _require(row.get("source_ordinal"), "source_ordinal")
                if not original_ordinal.isdecimal() or int(original_ordinal) <= 0:
                    raise ValueError("Original XML row ordinal must be positive")
                selected[source_key].add(int(original_ordinal))
            if count == 0:
                raise ValueError("No real contractual payment records were supplied")
        if _sha256(path) != expected_hash.lower():
            raise ValueError("Contractual ledger changed during partition preflight")
    return {key: frozenset(values) for key, values in selected.items()}


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
    verified_source_cache: dict[str, VerifiedContractualXMLSource] | None = None,
    selected_source_ordinals: dict[str, frozenset[int]] | None = None,
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
    needed_ordinals: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        source_key = _require(row.get("source_key"), "source_key")
        ordinal_text = _require(row.get("source_ordinal"), "source_ordinal")
        if not ordinal_text.isdecimal() or int(ordinal_text) <= 0:
            raise ValueError("Original XML row ordinal must be positive")
        needed_ordinals[source_key].add(int(ordinal_text))
    if selected_source_ordinals is not None:
        for source_key, requested in needed_ordinals.items():
            if not requested.issubset(selected_source_ordinals.get(source_key, frozenset())):
                raise ValueError("Contractual ledger row is absent from batch source selection")
    if not selected_sources.issubset(_SUPPORTED) or selected_sources != set(approved_xml_sha256):
        raise ValueError("Selected XML contractual sources and approved hashes disagree")
    source_entity_ids: set[str] = set()
    source_record_counts: dict[str, int] = {}
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
        cached = verified_source_cache.get(key) if verified_source_cache is not None else None
        target_ordinals = (
            selected_source_ordinals[key]
            if selected_source_ordinals is not None
            else frozenset(needed_ordinals[key])
        )
        if cached is not None:
            if (
                cached.path.resolve() != original.path.resolve()
                or cached.sha256 != actual_hash
                or cached.entity_id != original.header.id_entidad
            ):
                raise ValueError("Contractual XML changed between approved partitions")
            if needed_ordinals[key].issubset(cached.selected_ordinals):
                indexed = cached.indexed_rows
                source_record_counts[key] = cached.total_records
            else:
                target_ordinals = cached.selected_ordinals | target_ordinals
                cached = None
        if cached is None:
            indexed = {}
            original_count = 0
            raw_ids: set[str] = set()
            for ordinal, item in enumerate(reader.iter_records(original), 1):
                original_count = ordinal
                if not item.record_id.strip() or item.record_id in raw_ids:
                    raise ValueError("Original contractual XML contains ambiguous record IDs")
                raw_ids.add(item.record_id)
                if ordinal in target_ordinals:
                    indexed[ordinal] = item
            if reader.sha256(original.path) != actual_hash:
                raise ValueError("Contractual XML changed while indexing original source")
            source_record_counts[key] = original_count
            if verified_source_cache is not None:
                verified_source_cache[key] = VerifiedContractualXMLSource(
                    path=original.path,
                    sha256=actual_hash,
                    entity_id=original.header.id_entidad,
                    selected_ordinals=target_ordinals,
                    total_records=original_count,
                    indexed_rows=indexed,
                )
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
    for source_key in selected_sources:
        original = reader.resolve_source(key=source_key, cutoff_date=cutoff)
        if reader.sha256(original.path) != by_key[source_key][1]:
            raise ValueError("Contractual XML changed during payment reconciliation")
    return ApprovedXMLContractualSchedule(
        cutoff=cutoff,
        events=tuple(payments),
        source_hashes=tuple(sorted((key, info[1]) for key, info in by_key.items())),
        ledger_sha256=ledger_hash,
        included_source_records=tuple(sorted(contract_details)),
        source_entity_id=next(iter(source_entity_ids)),
        source_record_counts=tuple(sorted(source_record_counts.items())),
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
    source_record_counts: dict[str, int] = {}
    seen_files: set[str] = set()
    seen_records: set[tuple[str, int]] = set()
    seen_events: set[str] = set()
    source_entity_id: str | None = None
    events: list[LiquidityProjectionFlow] = []
    for item in partitions:
        if item.cutoff != cutoff or item.status != (
            "SELECTED_SOURCE_DATED_PAYMENTS_NOT_COMPLETE_PERIMETER"
        ):
            raise ValueError("Contractual payment partitions have conflicting cutoffs or status")
        if len(item.ledger_sha256) != 64 or item.ledger_sha256 in seen_files:
            raise ValueError("Contractual payment CSV partition is repeated")
        if not item.source_entity_id:
            raise ValueError("Contractual partition lacks original reporting entity")
        if source_entity_id is not None and item.source_entity_id != source_entity_id:
            raise ValueError("Approved contractual partitions belong to different entities")
        source_entity_id = item.source_entity_id
        seen_files.add(item.ledger_sha256)
        for key, digest in item.source_hashes:
            if key in source_hashes and source_hashes[key] != digest:
                raise ValueError("Conflicting source hashes across contractual partitions")
            source_hashes[key] = digest
        for key, total in item.source_record_counts:
            if key not in dict(item.source_hashes) or total < 0:
                raise ValueError("Contractual XML source count has no original source proof")
            if key in source_record_counts and source_record_counts[key] != total:
                raise ValueError("Contractual XML total source records conflict across partitions")
            source_record_counts[key] = total
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
    combined_hash = hashlib.sha256("\n".join(sorted(seen_files)).encode("ascii")).hexdigest()
    return ApprovedXMLContractualSchedule(
        cutoff=cutoff,
        events=tuple(events),
        source_hashes=tuple(sorted(source_hashes.items())),
        ledger_sha256=combined_hash,
        included_source_records=tuple(sorted(seen_records)),
        source_entity_id=source_entity_id,
        source_record_counts=tuple(sorted(source_record_counts.items())),
    )
