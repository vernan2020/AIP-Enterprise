"""Governed off-balance contingent liquidity stress from a reconciled register.

Outstanding commitments are possible uses of liquidity, not cash. No default
utilization rate or time distribution is applied: explicit, period-valid,
institution-approved per-scenario rules govern individual risk categories.
Neither a CSV hash nor typed approval references authenticate signatures.
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
    LiquidityFlowSide,
)
from aip.domain.liquidity.cashflow.services.sugef210_scenario_rules import (
    ApprovedScenarioRule,
    ReconciledBehavioralExposure,
    ScenarioGeneratedEvidence,
    generate_approved_scenario_events,
)

_FIELDS = (
    "commitment_reference",
    "account_code",
    "original_currency_code",
    "native_currency",
    "committed_limit",
    "already_disbursed",
    "restricted_amount",
    "available_undrawn",
    "expiration_date",
    "category",
    "nonduplication_reference",
    "source_evidence_reference",
)
_MAX_SOURCE = 20 * 1024 * 1024
_MAX_APPROVAL = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class OffBalanceScenarioIntake:
    evidence: ScenarioGeneratedEvidence
    source_sha256: str
    approval_sha256: str
    commitments_checked: int
    verified_undrawn_by_currency: tuple[tuple[str, Decimal], ...]
    status: str = "APPROVED_PARTIAL_OFFBALANCE_SCENARIO_NOT_CASH"


def _required(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Off-balance evidence is missing " + label)
    return value.strip()


def _amount(raw: Any) -> Decimal:
    value = _required(raw, "native balance")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Off-balance source contains an invalid amount") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Off-balance source amount must be finite and nonnegative")
    return number


def _date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(_required(value, label))
    except ValueError as exc:
        raise ValueError("Off-balance scenario dates must be ISO") from exc


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    doc: dict[str, Any] = {}
    for key, value in items:
        if key in doc:
            raise ValueError("Duplicate off-balance authorization JSON key")
        doc[key] = value
    return doc


def read_governed_offbalance_scenario(
    *,
    cutoff: date,
    scenario: str,
    source_csv: str | Path,
    approval_json: str | Path,
    existing_contractual_source_refs: frozenset[str] = frozenset(),
    already_in_opening: frozenset[str] = frozenset(),
) -> OffBalanceScenarioIntake:
    """Turn only specifically reconciled undrawn commitments into stress events.

    Source CSV must be a real independently validated off-balance register. An
    approval manifest explicitly identifies its SHA-256, native currency mapping,
    categories, scenario, and signed-off risk factors with date-specific timing.
    """
    source = Path(source_csv)
    approval = Path(approval_json)
    if source.resolve() == approval.resolve():
        raise ValueError("Off-balance register and policy approval must be separate files")
    if not source.is_file() or source.stat().st_size > _MAX_SOURCE:
        raise ValueError("Off-balance source register missing or oversized")
    if not approval.is_file() or approval.stat().st_size > _MAX_APPROVAL:
        raise ValueError("Off-balance approval missing or oversized")
    try:
        document = json.loads(
            approval.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Off-balance approval is not valid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("Off-balance approval must be a JSON object")
    if _required(document.get("schema"), "schema") != "SUGEF210_OFFBALANCE_SCENARIO_V1":
        raise ValueError("Unsupported off-balance policy schema")
    if _date(document.get("cutoff"), "cutoff") != cutoff:
        raise ValueError("Off-balance policy cutoff differs from liquidity projection")
    if _required(document.get("scenario"), "scenario") != scenario:
        raise ValueError("Off-balance policy scenario differs from liquidity projection")
    actual_sha = _hash(source)
    if _required(document.get("source_sha256"), "source_sha256").lower() != actual_sha:
        raise ValueError("Off-balance register hash no longer matches approved source")
    original_codes = document.get("approved_currency_codes")
    if not isinstance(original_codes, dict) or not original_codes or any(
        not isinstance(key, str)
        or not key.strip()
        or value not in {"CRC", "USD"}
        for key, value in original_codes.items()
    ):
        raise ValueError("Off-balance native currency mapping has no approved evidence")
    valid_account_codes = document.get("approved_account_codes")
    if not isinstance(valid_account_codes, list) or not valid_account_codes or any(
        not isinstance(code, str) or not code.strip() for code in valid_account_codes
    ) or len(set(valid_account_codes)) != len(valid_account_codes):
        raise ValueError("Approved off-balance accounting accounts are required")
    _required(document.get("classification_approval"), "classification approval")
    _required(document.get("nonduplication_approval"), "nonduplication approval")
    _required(document.get("currency_mapping_approval"), "currency mapping approval")
    rules = document.get("approved_rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("Off-balance scenario has no approved utilization rules")

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        input_rows = csv.DictReader(handle)
        if (
            input_rows.fieldnames is None
            or len(input_rows.fieldnames) != len(set(input_rows.fieldnames))
            or set(input_rows.fieldnames) != set(_FIELDS)
        ):
            raise ValueError("Off-balance register must contain exact unique columns")
        rows = list(input_rows)
    if not rows or len(rows) > 250000:
        raise ValueError("Off-balance source register is empty or too large")
    candidates: list[ReconciledBehavioralExposure] = []
    verified_totals = {"CRC": Decimal(0), "USD": Decimal(0)}
    seen_references: set[str] = set()
    categories: set[str] = set()
    earliest_expiration_by_category: dict[str, date] = {}
    for row in rows:
        name = _required(row.get("commitment_reference"), "commitment_reference")
        account = _required(row.get("account_code"), "account_code")
        source_code = _required(row.get("original_currency_code"), "original_currency_code")
        native_currency = _required(row.get("native_currency"), "native_currency")
        category = _required(row.get("category"), "category")
        rec = _required(row.get("nonduplication_reference"), "nonduplication_reference")
        orig_evidence = _required(row.get("source_evidence_reference"), "source evidence")
        if account not in valid_account_codes or original_codes.get(source_code) != native_currency:
            raise ValueError("Off-balance source accounting account or native currency unapproved")
        if name in seen_references or rec in seen_references:
            raise ValueError("Duplicate off-balance commitment or reconciliation")
        if name in already_in_opening or name in existing_contractual_source_refs:
            raise ValueError("Undrawn commitment already appears in opening or contractual cash")
        seen_references.update((name, rec))
        expires = _date(row.get("expiration_date"), "expiration_date")
        if expires <= cutoff:
            raise ValueError("Expired off-balance commitment cannot be called")
        committed = _amount(row.get("committed_limit"))
        utilized = _amount(row.get("already_disbursed"))
        restricted = _amount(row.get("restricted_amount"))
        remaining = _amount(row.get("available_undrawn"))
        if committed <= 0 or utilized + restricted > committed:
            raise ValueError("Undrawn commitment register has impossible balances")
        if remaining != committed - utilized - restricted:
            raise ValueError("Available undrawn exposure fails source limit reconciliation")
        categories.add(category)
        if category not in earliest_expiration_by_category:
            earliest_expiration_by_category[category] = expires
        else:
            earliest_expiration_by_category[category] = min(
                earliest_expiration_by_category[category], expires
            )
        verified_totals[native_currency] += remaining
        candidates.append(
            ReconciledBehavioralExposure(
                reference=name,
                source_reference=f"OFFBALANCE_REGISTER:{actual_sha}:{orig_evidence}:{account}",
                source_cutoff=cutoff,
                currency=native_currency,
                amount=remaining,
                category=category,
                nonduplication_reference=rec,
            )
        )

    parameters: list[ApprovedScenarioRule] = []
    used_categories: set[str] = set()
    for item in rules:
        if not isinstance(item, dict):
            raise ValueError("Off-balance policy rule must be a structured object")
        category = _required(item.get("exposure_category"), "exposure_category")
        if category not in categories or category in used_categories:
            raise ValueError("Missing source category or repeated off-balance utilization rule")
        used_categories.add(category)
        if item.get("explicitly_approved") is not True:
            raise ValueError("Off-balance utilization requires an explicit institutional approval")
        day = item.get("projection_day")
        if type(day) is not int:
            raise ValueError("Off-balance utilization projection day must be an integer")
        if not 0 <= day <= 365:
            raise ValueError("Off-balance scenario must fit fixed 365-day horizon")
        if cutoff.toordinal() + day > earliest_expiration_by_category[category].toordinal():
            raise ValueError("Contingent drawdown cannot occur after commitment expiration")
        factor = _amount(item.get("factor"))
        if factor > 1:
            raise ValueError("Off-balance stress factor must not exceed 100 percent")
        parameters.append(
            ApprovedScenarioRule(
                reference=_required(item.get("reference"), "rule reference"),
                scenario=scenario,
                exposure_category=category,
                factor=factor,
                projection_day=day,
                flow_side=LiquidityFlowSide.OUTFLOW,
                area=LiquidityBalanceArea.OFF_BALANCE,
                rationale=_required(item.get("rationale"), "rationale"),
                approval_reference=_required(item.get("approval_reference"), "approval reference"),
                source_reference=(
                    f"OFFBALANCE_RULE:{_hash(approval)}:"
                    f"{_required(item.get('source_reference'), 'rule source')}"
                ),
                version=_required(item.get("version"), "rule version"),
                approved_on=_date(item.get("approved_on"), "approved_on"),
                valid_from=_date(item.get("valid_from"), "valid_from"),
                valid_to=_date(item.get("valid_to"), "valid_to"),
                explicitly_approved=True,
            )
        )
    if used_categories != categories:
        raise ValueError("Unapproved off-balance exposure category cannot be silently omitted")
    result = generate_approved_scenario_events(
        cutoff=cutoff,
        scenario=scenario,
        exposures=candidates,
        rules=parameters,
        contractually_scheduled_exposure_refs=existing_contractual_source_refs,
    )
    return OffBalanceScenarioIntake(
        evidence=result,
        source_sha256=actual_sha,
        approval_sha256=_hash(approval),
        commitments_checked=len(candidates),
        verified_undrawn_by_currency=tuple(sorted(verified_totals.items())),
    )
