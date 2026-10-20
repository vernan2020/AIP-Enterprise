"""Governed demand-deposit outflows from the original configured CONFIA 210 XML.

A sight balance is an *exposure*, never a contractual withdrawal. Only exact
account/type codes and scenario-specific approved, time-banded runoff factors
can create liability outflows. Native currencies remain unconverted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityFlowSide,
)
from aip.domain.liquidity.cashflow.services.sugef210_scenario_rules import (
    ApprovedScenarioRule,
    ReconciledBehavioralExposure,
    ScenarioGeneratedEvidence,
    generate_approved_scenario_events,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader

_MAX_APPROVAL = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class DemandDepositRunoffIntake:
    evidence: ScenarioGeneratedEvidence
    cutoff: date
    xml_sha256: str
    approved_accounts_seen: int
    excluded_xml_records: int
    source_native_balances: tuple[tuple[str, Decimal], ...]
    included_source_ordinals: frozenset[int]
    reconciled_native_groups: tuple[tuple[str, str, str, int, Decimal], ...] = ()
    status: str = "APPROVED_SELECTED_DEMAND_DEPOSITS_NOT_COMPLETE_COVERAGE"


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, value in pairs:
        if name in document:
            raise ValueError("Duplicate field in demand-deposit approval JSON")
        document[name] = value
    return document


def _required(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing approved demand-deposit field: " + field)
    return value.strip()


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(_required(value, field))
    except ValueError as exc:
        raise ValueError("Invalid demand-deposit ISO date: " + field) from exc


def _amount(value: Any) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Demand-deposit source requires an original decimal balance")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Original demand-deposit balance is not numeric") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Demand-deposit balance must be finite and nonnegative")
    return amount


def read_approved_demand_deposit_runoff(
    *,
    reader: XMLConfiaMonthlySourceReader,
    cutoff: date,
    scenario: str,
    approval_file: str | Path,
    contractually_scheduled_ordinals: frozenset[int] = frozenset(),
    already_in_opening: frozenset[str] = frozenset(),
) -> DemandDepositRunoffIntake:
    """Match exact native XML 210 records to separate ALCO/Treasury scenario policy."""
    path = Path(approval_file)
    if not path.is_file() or path.stat().st_size > _MAX_APPROVAL:
        raise ValueError("Demand-deposit approval missing or oversized")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_fields,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON input")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Demand-deposit approval must be valid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("Demand-deposit policy must be a JSON object")
    if _required(document.get("schema"), "schema") != "SUGEF210_DEMAND_RUNOFF_V1":
        raise ValueError("Unrecognized approved demand-deposit policy schema")
    if _date(document.get("cutoff"), "cutoff") != cutoff:
        raise ValueError("Demand-deposit source cutoff differs from projection")
    if _required(document.get("scenario"), "scenario") != scenario:
        raise ValueError("Demand-deposit runoff policy cannot be reused in another scenario")
    entity = _required(document.get("entity_id"), "entity_id")
    expected_hash = _required(document.get("xml_sha256"), "xml_sha256")
    source = reader.resolve_source(key="CAPTACIONES", cutoff_date=cutoff)
    if source.header.id_entidad != entity or (
        source.header.periodo.year,
        source.header.periodo.month,
    ) != (cutoff.year, cutoff.month):
        raise ValueError("Demand-deposit XML entity or source period does not match approval")
    original_hash = reader.sha256(source.path)
    if len(expected_hash) != 64 or expected_hash.lower() != original_hash:
        raise ValueError("Demand-deposit source XML hash changed since approval")

    accounts = document.get("approved_sight_account_codes")
    types = document.get("approved_sight_type_codes")
    codes = document.get("approved_currency_codes")
    if (
        not isinstance(accounts, list)
        or not accounts
        or not isinstance(types, list)
        or not types
        or not isinstance(codes, dict)
        or not codes
        or any(not isinstance(code, str) or not code.strip() for code in accounts + types)
        or len(set(accounts)) != len(accounts)
        or len(set(types)) != len(types)
        or any(
            not isinstance(code, str) or not code.strip() or currency not in {"CRC", "USD"}
            for code, currency in codes.items()
        )
    ):
        raise ValueError("Demand-deposit original account, type and currency catalogs required")
    classification = _required(document.get("classification_approval"), "classification_approval")
    currency_approval = _required(
        document.get("currency_mapping_approval"), "currency_mapping_approval"
    )
    nonduplication = _required(document.get("nonduplication_approval"), "nonduplication_approval")
    rule_items = document.get("approved_rules")
    if not isinstance(rule_items, list) or not rule_items:
        raise ValueError("Demand-deposit runoffs require approved dated scenario rules")

    source_reconciliation = document.get("approved_native_balance_reconciliation")
    if not isinstance(source_reconciliation, list) or not source_reconciliation:
        raise ValueError("Approved independent native balance reconciliation is mandatory")
    expected: dict[tuple[str, str, str], tuple[int, Decimal]] = {}
    for entry in source_reconciliation:
        if not isinstance(entry, dict):
            raise ValueError("Native deposit reconciliation must contain structured account records")
        account = _required(entry.get("account_code"), "reconciled account")
        sight_type = _required(entry.get("type_code"), "reconciled type")
        original_code = _required(entry.get("currency_source_code"), "reconciled currency")
        currency = _required(entry.get("currency"), "reconciled ISO currency")
        _required(entry.get("reconciliation_reference"), "independent reconciliation reference")
        count = entry.get("source_record_count")
        if type(count) is not int or count <= 0:
            raise ValueError("Source reconciliation requires a positive record count")
        amount = _amount(entry.get("original_native_balance"))
        key = (account, sight_type, original_code)
        if (
            key in expected
            or account not in accounts
            or sight_type not in types
            or codes.get(original_code) != currency
        ):
            raise ValueError("Native account/type/currency reconciliation is duplicated or unapproved")
        expected[key] = (count, amount)

    exposures: list[ReconciledBehavioralExposure] = []
    native_totals = {"CRC": Decimal(0), "USD": Decimal(0)}
    included: set[int] = set()
    seen_ids: set[str] = set()
    excluded = 0
    categories: set[str] = set()
    actual: dict[tuple[str, str, str], tuple[int, Decimal]] = {}
    for ordinal, record in enumerate(reader.iter_records(source), start=1):
        values = record.values
        account = (values.get("CuentaContablePrincipal") or "").strip()
        sight_type = (values.get("TipoCuenta") or "").strip()
        if account not in accounts or sight_type not in types:
            excluded += 1
            continue
        if (values.get("FechaVencimiento") or "").strip():
            raise ValueError("Contractually dated deposit cannot be reclassified as sight runoff")
        if not record.record_id.strip() or record.record_id in seen_ids:
            raise ValueError("Approved sight XML contains absent or repeated source IDs")
        seen_ids.add(record.record_id)
        if ordinal in contractually_scheduled_ordinals:
            raise ValueError("Demand-deposit record already has scheduled contractual payments")
        currency_code = _required(values.get("TipoMonedaObligacion"), "original currency code")
        currency = codes.get(currency_code)
        if currency is None:
            raise ValueError("Original demand-deposit currency lacks approved mapping")
        source_balance = _amount(values.get("SaldoPrincipal"))
        native_key = (account, sight_type, currency_code)
        if native_key not in expected:
            raise ValueError("Selected source account/type/currency lacks independent reconciliation")
        record_count, prior_total = actual.get(native_key, (0, Decimal(0)))
        actual[native_key] = (record_count + 1, prior_total + source_balance)
        reference = f"CONFIA210:SIGHT:{original_hash}:{ordinal}:{record.record_id}"
        if reference in already_in_opening:
            raise ValueError("Demand-deposit source was already recognized in opening")
        included.add(ordinal)
        native_totals[currency] += source_balance
        category = f"SIGHT:{account}:{sight_type}:{currency}"
        categories.add(category)
        if not source_balance:
            continue
        exposures.append(
            ReconciledBehavioralExposure(
                reference=reference,
                source_reference=(
                    f"CONFIA210:{original_hash}:{entity}:ACCOUNT:{account}:"
                    f"CLASSIFICATION:{classification}:CURRENCY:{currency_approval}"
                ),
                source_cutoff=cutoff,
                currency=currency,
                amount=source_balance,
                category=category,
                nonduplication_reference=f"{nonduplication}:{ordinal}:{record.record_id}",
            )
        )
    if reader.sha256(source.path) != original_hash:
        raise ValueError("Demand-deposit XML changed during reconciliation")
    if not included:
        raise ValueError("No approved demand-deposit source accounts match actual XML")
    if actual != expected:
        raise ValueError(
            "Approved demand-deposit record counts and native balance totals "
            "do not reconcile exactly to source XML 210"
        )

    approved: list[ApprovedScenarioRule] = []
    covered: set[str] = set()
    for item in rule_items:
        if not isinstance(item, dict):
            raise ValueError("Demand-deposit rule must be a JSON object")
        category = _required(item.get("exposure_category"), "exposure_category")
        if category not in categories:
            raise ValueError("Runoff rule category does not match any approved sight XML exposure")
        covered.add(category)
        if item.get("explicitly_approved") is not True:
            raise ValueError("Demand-deposit runoff requires explicit ALCO/Treasury approval")
        day = item.get("projection_day")
        if type(day) is not int:
            raise ValueError("Runoff projection day must be an integer")
        approved.append(
            ApprovedScenarioRule(
                reference=_required(item.get("reference"), "reference"),
                scenario=scenario,
                exposure_category=category,
                factor=_amount(item.get("factor")),
                projection_day=day,
                flow_side=LiquidityFlowSide.OUTFLOW,
                area=LiquidityBalanceArea.LIABILITY,
                rationale=_required(item.get("rationale"), "rationale"),
                approval_reference=_required(item.get("approval_reference"), "approval_reference"),
                source_reference=(
                    f"APPROVED_SIGHT_POLICY:{original_hash}:"
                    f"{_required(item.get('source_reference'), 'source_reference')}"
                ),
                version=_required(item.get("version"), "version"),
                approved_on=_date(item.get("approved_on"), "approved_on"),
                valid_from=_date(item.get("valid_from"), "valid_from"),
                valid_to=_date(item.get("valid_to"), "valid_to"),
                explicitly_approved=True,
            )
        )
    if covered != categories:
        raise ValueError("Not every included sight category has an approved runoff rule")
    generated = generate_approved_scenario_events(
        cutoff=cutoff,
        scenario=scenario,
        exposures=exposures,
        rules=approved,
    )
    return DemandDepositRunoffIntake(
        evidence=generated,
        cutoff=cutoff,
        xml_sha256=original_hash,
        approved_accounts_seen=len(included),
        excluded_xml_records=excluded,
        source_native_balances=tuple(sorted(native_totals.items())),
        included_source_ordinals=frozenset(included),
        reconciled_native_groups=tuple(
            (account, sight_type, currency_code, actual[key][0], actual[key][1])
            for key in sorted(actual)
            for account, sight_type, currency_code in (key,)
        ),
    )
