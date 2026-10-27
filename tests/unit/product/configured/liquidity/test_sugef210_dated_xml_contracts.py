"""Independent dated contractual ledger and real XML reconciliation tests."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaHeader,
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)
from aip.product.configured.liquidity.sugef210_dated_xml_contracts import (
    VerifiedContractualXMLSource,
    import_approved_xml_contractual_payments,
    merge_approved_xml_contractual_schedules,
    select_approved_partition_source_ordinals,
)

CUTOFF = date(2026, 9, 30)
HEADERS = (
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
SRC = {
    "CREDIT": {
        "SaldoPrincipalOperacionCrediticia": "200",
        "TipoMonedaOperacion": "1",
        "CuentaContablePrincipal": "131",
        "FechaVencimiento": "30/09/2027",
    },
    "CAPTACIONES": {
        "SaldoPrincipal": "85",
        "TipoMonedaObligacion": "2",
        "CuentaContablePrincipal": "211",
        "FechaVencimiento": "30/09/2027",
        "TipoCuenta": "TERM",
    },
    "BORROWING": {
        "SaldoPrincipal": "45",
        "TipoMonedaObligacion": "1",
        "CuentaContablePrincipal": "221",
        "FechaVencimiento": "30/09/2027",
    },
}


class Reader:
    def __init__(self, root: Path):
        self.root = root
        for key in SRC:
            (root / (key + ".xml")).write_bytes(key.encode())

    def resolve_source(self, *, key: str, cutoff_date: date):
        assert cutoff_date == CUTOFF
        return XMLConfiaResolvedSource(
            key=key,
            path=self.root / (key + ".xml"),
            header=XMLConfiaHeader(
                clase_dato="1",
                archivo=key,
                periodo=date(2026, 9, 1),
                id_entidad="TEST",
                tipo_carga="1",
                tipo_moneda="1",
            ),
        )

    def iter_records(self, source):
        yield XMLConfiaRecord(
            record_id="SRC-" + source.key,
            action="insertar",
            values=SRC[source.key],
        )

    @staticmethod
    def sha256(path: Path):
        return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(key, *, payment="P1", flow_type="PRINCIPAL", amount=None):
    raw = SRC[key]
    return {
        "source_key": key,
        "source_ordinal": "1",
        "source_record_id": "SRC-" + key,
        "account_code": raw["CuentaContablePrincipal"],
        "original_currency_code": (
            raw["TipoMonedaOperacion"] if key == "CREDIT" else raw["TipoMonedaObligacion"]
        ),
        "currency": "USD" if key == "CAPTACIONES" else "CRC",
        "original_principal": (
            raw["SaldoPrincipalOperacionCrediticia"] if key == "CREDIT" else raw["SaldoPrincipal"]
        ),
        "maturity_date": "2027-09-30",
        "payment_reference": payment,
        "payment_date": (CUTOFF + timedelta(days=31)).isoformat(),
        "flow_type": flow_type,
        "amount": amount
        or (raw["SaldoPrincipalOperacionCrediticia"] if key == "CREDIT" else raw["SaldoPrincipal"]),
        "availability_reference": "TEST-CUSTODIAN-CONTRACT-" + key,
    }


def _import(tmp_path, rows, *, approve_terms=frozenset({"TERM"})):
    reader = Reader(tmp_path)
    ledger = tmp_path / "contractual-payments.csv"
    with ledger.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return import_approved_xml_contractual_payments(
        reader=reader,
        cutoff=CUTOFF,
        ledger_file=ledger,
        expected_ledger_sha256=Reader.sha256(ledger),
        approved_xml_sha256={
            key: Reader.sha256(tmp_path / (key + ".xml"))
            for key in {row["source_key"] for row in rows}
        },
        approved_currency_codes={"1": "CRC", "2": "USD"},
        approved_term_deposit_codes=approve_terms,
        source_payment_approval="TEST-INSTITUTIONAL-DATED-LEDGER-APPROVAL",
        settlement_approval="TEST-TREASURY-PAYMENT-CERTIFICATION",
        nonduplication_reference="TEST-LIQUIDITY-SOURCE-NONDUP",
    )


def test_three_xml_perimeters_preserve_original_native_cash_dates_and_sides(tmp_path):
    result = _import(tmp_path, [_row(key) for key in SRC])
    assert len(result.events) == 3
    assert len(result.source_hashes) == 3
    assert result.events[0].currency == "CRC"
    assert result.events[1].currency == "USD"
    assert result.events[1].amount == 85
    assert result.events[2].amount == 45
    assert [e.area.value for e in result.events] == ["ASSET", "LIABILITY", "LIABILITY"]
    assert [e.side.value for e in result.events] == ["INFLOW", "OUTFLOW", "OUTFLOW"]
    assert result.certifies_entire_perimeter is False
    assert result.source_coverage == (
        ("BORROWING", 1, 1),
        ("CAPTACIONES", 1, 1),
        ("CREDIT", 1, 1),
    )


def test_full_principal_reconciliation_allows_separate_contractual_coupon(tmp_path):
    result = _import(
        tmp_path,
        [
            _row("CREDIT", amount="125", payment="PRIN-A"),
            _row("CREDIT", amount="75", payment="PRIN-B"),
            _row("CREDIT", flow_type="INTEREST", amount="5.5", payment="COUPON"),
        ],
    )
    assert len(result.events) == 3
    assert sum(x.amount for x in result.events) == 205.5


def test_partial_credit_schedule_or_wrong_original_xml_balance_fails(tmp_path):
    with pytest.raises(ValueError, match="does not reconcile"):
        _import(tmp_path, [_row("CREDIT", amount="150")])
    with pytest.raises(ValueError, match="disagrees with XML"):
        _import(tmp_path, [{**_row("CREDIT"), "original_principal": "201"}])


def test_demand_deposits_never_inferred_matured_and_native_currency_required(tmp_path):
    with pytest.raises(ValueError, match="Demand deposits"):
        _import(tmp_path, [_row("CAPTACIONES")], approve_terms=frozenset())
    with pytest.raises(ValueError, match="native currency"):
        _import(tmp_path, [{**_row("CAPTACIONES"), "currency": "CRC"}])


def test_reject_duplicate_event_and_unverified_source_maturity(tmp_path):
    with pytest.raises(ValueError, match="Duplicated contractual"):
        _import(tmp_path, [_row("CREDIT"), _row("CREDIT")])
    with pytest.raises(ValueError, match="maturity differs"):
        _import(tmp_path, [{**_row("BORROWING"), "maturity_date": "2027-10-01"}])


def test_mixed_institution_entities_are_rejected(monkeypatch, tmp_path):
    from sys import modules

    class MixedReader(Reader):
        def resolve_source(self, *, key, cutoff_date):
            original = super().resolve_source(key=key, cutoff_date=cutoff_date)
            if key == "BORROWING":
                return replace(original, header=replace(original.header, id_entidad="OTHER-ENTITY"))
            return original

    monkeypatch.setattr(modules[__name__], "Reader", MixedReader)
    with pytest.raises(ValueError, match="different reporting entities"):
        _import(tmp_path, [_row("CREDIT"), _row("BORROWING")])


def test_original_xml_duplicate_record_ids_block_cash(monkeypatch, tmp_path):
    from sys import modules

    class DuplicateReader(Reader):
        def iter_records(self, source):
            yield from super().iter_records(source)
            yield from super().iter_records(source)

    monkeypatch.setattr(modules[__name__], "Reader", DuplicateReader)
    with pytest.raises(ValueError, match="ambiguous record IDs"):
        _import(tmp_path, [_row("CREDIT")])


def test_partitioned_contractual_schedules_merge_without_new_certification(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = _import(first_dir, [_row("CREDIT")])
    second = _import(second_dir, [_row("BORROWING")])
    joined = merge_approved_xml_contractual_schedules(cutoff=CUTOFF, schedules=(first, second))
    assert len(joined.events) == 2
    assert len(joined.included_source_records) == 2
    assert {event.area.value for event in joined.events} == {"ASSET", "LIABILITY"}
    assert joined.certifies_entire_perimeter is False
    assert joined.ledger_sha256 not in {first.ledger_sha256, second.ledger_sha256}


def test_partitioned_contracts_reject_duplicate_sources_and_contracts(tmp_path):
    part_dir = tmp_path / "part"
    part_dir.mkdir()
    first = _import(part_dir, [_row("CREDIT")])
    with pytest.raises(ValueError, match="repeated"):
        merge_approved_xml_contractual_schedules(cutoff=CUTOFF, schedules=(first, first))
    duplicated = replace(first, ledger_sha256="b" * 64)
    with pytest.raises(ValueError, match="operation repeats"):
        merge_approved_xml_contractual_schedules(cutoff=CUTOFF, schedules=(first, duplicated))


def test_partition_merge_rejects_conflicting_xml_and_cutoffs(tmp_path):
    one_dir = tmp_path / "p1"
    two_dir = tmp_path / "p2"
    one_dir.mkdir()
    two_dir.mkdir()
    first = _import(one_dir, [_row("CREDIT")])
    second = _import(two_dir, [_row("CREDIT")])
    conflict = replace(second, ledger_sha256="d" * 64, source_hashes=(("CREDIT", "c" * 64),))
    with pytest.raises(ValueError, match="Conflicting source hashes"):
        merge_approved_xml_contractual_schedules(cutoff=CUTOFF, schedules=(first, conflict))
    with pytest.raises(ValueError, match="cutoffs"):
        merge_approved_xml_contractual_schedules(
            cutoff=CUTOFF, schedules=(replace(first, cutoff=date(2026, 8, 31)),)
        )


class CountingReader(Reader):
    """Synthetic reader can prove XML parse is reused across approved partitions."""

    def __init__(self, root: Path):
        super().__init__(root)
        self.parses: dict[str, int] = {}

    def iter_records(self, source):
        self.parses[source.key] = self.parses.get(source.key, 0) + 1
        yield from super().iter_records(source)


def _cached_partition(reader, tmp_path, *, suffix, cache, amount="200"):
    ledger = tmp_path / f"partition-{suffix}.csv"
    with ledger.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow(_row("CREDIT", payment=suffix, amount=amount))
    return import_approved_xml_contractual_payments(
        reader=reader,
        cutoff=CUTOFF,
        ledger_file=ledger,
        expected_ledger_sha256=Reader.sha256(ledger),
        approved_xml_sha256={"CREDIT": Reader.sha256(tmp_path / "CREDIT.xml")},
        approved_currency_codes={"1": "CRC", "2": "USD"},
        source_payment_approval="TEST-CONTRACTUAL-SCHEDULE",
        settlement_approval="TEST-SETTLEMENT",
        nonduplication_reference=f"PARTITION-{suffix}",
        verified_source_cache=cache,
    )


def test_verified_xml_cache_avoids_reparsing_same_source_between_partitions(tmp_path):
    reader = CountingReader(tmp_path)
    cache: dict[str, VerifiedContractualXMLSource] = {}
    first = _cached_partition(reader, tmp_path, suffix="A", cache=cache)
    second = _cached_partition(reader, tmp_path, suffix="B", cache=cache)
    assert reader.parses == {"CREDIT": 1}
    assert list(cache) == ["CREDIT"]
    assert first.source_entity_id == second.source_entity_id == "TEST"
    assert first.events[0].source != second.events[0].source
    assert first.events[0].amount == second.events[0].amount == 200
    assert first.certifies_entire_perimeter is False


def test_verified_xml_cache_fails_closed_when_source_changes_between_partitions(tmp_path):
    reader = CountingReader(tmp_path)
    cache: dict[str, VerifiedContractualXMLSource] = {}
    _cached_partition(reader, tmp_path, suffix="A", cache=cache)
    (tmp_path / "CREDIT.xml").write_bytes(b"modified-after-first-signed-ledger")
    with pytest.raises(ValueError, match="changed after approval"):
        _cached_partition(reader, tmp_path, suffix="B", cache=cache)
    assert reader.parses == {"CREDIT": 1}


def test_cached_source_path_cannot_switch_without_invalidating_snapshot(tmp_path):
    reader = CountingReader(tmp_path)
    cache: dict[str, VerifiedContractualXMLSource] = {}
    _cached_partition(reader, tmp_path, suffix="A", cache=cache)
    cache["CREDIT"] = replace(cache["CREDIT"], path=tmp_path / "SOME-OTHER-XML.xml")
    with pytest.raises(ValueError, match="changed between approved partitions"):
        _cached_partition(reader, tmp_path, suffix="B", cache=cache)


def test_partition_merge_rejects_different_institution_entity_ids(tmp_path):
    folder = tmp_path / "entity"
    folder.mkdir()
    first = _import(folder, [_row("CREDIT")])
    second = replace(
        first,
        ledger_sha256="f" * 64,
        source_entity_id="FOREIGN-ENTITY",
        included_source_records=(("BORROWING", 7),),
    )
    with pytest.raises(ValueError, match="different entities"):
        merge_approved_xml_contractual_schedules(cutoff=CUTOFF, schedules=(first, second))


class ManyRowReader(Reader):
    """Large synthetic XML stream with a tiny original-contract selection."""

    def __init__(self, root: Path, *, duplicate_unselected: bool = False):
        super().__init__(root)
        self.parses = 0
        self.duplicate_unselected = duplicate_unselected

    def iter_records(self, source):
        self.parses += 1
        for ordinal in range(1, 201):
            record_id = f"SOURCE-{ordinal}"
            if self.duplicate_unselected and ordinal == 150:
                record_id = "SOURCE-149"
            yield XMLConfiaRecord(
                record_id=record_id,
                action="insertar",
                values=SRC[source.key],
            )


def test_batch_source_selection_keeps_only_required_original_xml_rows(tmp_path):
    reader = ManyRowReader(tmp_path)
    ledgers = []
    for ordinal in (2, 199):
        ledger = tmp_path / f"source-ordinal-{ordinal}.csv"
        with ledger.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerow(
                {
                    **_row("CREDIT", payment=f"PAY-{ordinal}"),
                    "source_ordinal": str(ordinal),
                    "source_record_id": f"SOURCE-{ordinal}",
                }
            )
        ledgers.append((ledger, Reader.sha256(ledger)))
    ordinals = select_approved_partition_source_ordinals(ledgers)
    assert ordinals == {"CREDIT": frozenset({2, 199})}
    cache: dict[str, VerifiedContractualXMLSource] = {}
    partitions = []
    for index, (ledger, digest) in enumerate(ledgers):
        result = import_approved_xml_contractual_payments(
            reader=reader,
            cutoff=CUTOFF,
            ledger_file=ledger,
            expected_ledger_sha256=digest,
            approved_xml_sha256={"CREDIT": Reader.sha256(tmp_path / "CREDIT.xml")},
            approved_currency_codes={"1": "CRC"},
            source_payment_approval="TEST-DATED-SCHEDULE",
            settlement_approval="TEST-SETTLEMENT",
            nonduplication_reference=f"BATCH-{index}",
            verified_source_cache=cache,
            selected_source_ordinals=ordinals,
        )
        assert len(result.events) == 1
        partitions.append(result)
    combined = merge_approved_xml_contractual_schedules(
        cutoff=CUTOFF, schedules=partitions
    )
    assert combined.source_coverage == (("CREDIT", 2, 200),)
    assert combined.certifies_entire_perimeter is False
    assert reader.parses == 1
    assert cache["CREDIT"].selected_ordinals == frozenset({2, 199})
    assert sorted(cache["CREDIT"].indexed_rows) == [2, 199]


def test_unselected_original_id_ambiguity_still_blocks_batch_source(tmp_path):
    reader = ManyRowReader(tmp_path, duplicate_unselected=True)
    ledger = tmp_path / "selected.csv"
    with ledger.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow(
            {
                **_row("CREDIT"),
                "source_ordinal": "2",
                "source_record_id": "SOURCE-2",
            }
        )
    selected = select_approved_partition_source_ordinals([(ledger, Reader.sha256(ledger))])
    with pytest.raises(ValueError, match="ambiguous record IDs"):
        import_approved_xml_contractual_payments(
            reader=reader,
            cutoff=CUTOFF,
            ledger_file=ledger,
            expected_ledger_sha256=Reader.sha256(ledger),
            approved_xml_sha256={"CREDIT": Reader.sha256(tmp_path / "CREDIT.xml")},
            approved_currency_codes={"1": "CRC"},
            source_payment_approval="TEST-APPROVED-PAYMENTS",
            settlement_approval="TEST-SETTLEMENT",
            nonduplication_reference="TEST-UNIQUE",
            selected_source_ordinals=selected,
        )


def test_contractual_batch_selection_fails_closed_for_changed_signed_csv(tmp_path):
    ledger = tmp_path / "approved.csv"
    with ledger.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow(_row("CREDIT"))
    old_hash = Reader.sha256(ledger)
    ledger.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after approval"):
        select_approved_partition_source_ordinals([(ledger, old_hash)])



def test_contractual_partition_source_totals_conflict_fails_closed(tmp_path):
    first = _import(tmp_path, [_row("CREDIT")])
    inconsistent = replace(
        first,
        ledger_sha256="f" * 64,
        source_record_counts=(("CREDIT", 2),),
    )
    with pytest.raises(ValueError, match="total source records conflict"):
        merge_approved_xml_contractual_schedules(
            cutoff=CUTOFF, schedules=(first, inconsistent)
        )


def test_contractual_coverage_rejects_more_selected_than_original_xml(tmp_path):
    original = _import(tmp_path, [_row("CREDIT")])
    corrupt = replace(original, source_record_counts=(("CREDIT", 0),))
    with pytest.raises(ValueError, match="exceeds original"):
        _ = corrupt.source_coverage
