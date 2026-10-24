"""Configured SUGEF 2-10 opening-cash session with actual XML and separate bank evidence.

All paths are local configured institutional files. Never send source records to
GitHub, never infer withdrawals from demand balances and never represent a
manifest or a document hash as a bank's cryptographic signature.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.domain.liquidity.cashflow.services.sugef210_scenario_rules import (
    ScenarioGeneratedEvidence,
)
from aip.product.configured.irrbb.investment_master_discovery import (
    resolve_exact_cutoff_master,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.configured.liquidity.financial_plan_cashflow_bridge import (
    read_approved_financial_plan_overlay,
)
from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentCurrentAccountPolicy,
    audit_investment_current_accounts,
)
from aip.product.configured.liquidity.sugef210_approved_master_principal import (
    ApprovedMasterPrincipalPosition,
    admit_approved_master_principal,
)
from aip.product.configured.liquidity.sugef210_dated_xml_contracts import (
    import_approved_xml_contractual_payments,
    merge_approved_xml_contractual_schedules,
)
from aip.product.configured.liquidity.sugef210_demand_deposit_runoff import (
    read_approved_demand_deposit_runoff,
)
from aip.product.configured.liquidity.sugef210_master_coupon_schedule import (
    read_approved_master_coupons,
)
from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    build_master_principal_evidence,
)
from aip.product.configured.liquidity.sugef210_offbalance_scenario_source import (
    read_governed_offbalance_scenario,
)
from aip.product.configured.liquidity.sugef210_projection_assembler import (
    InstitutionalLiquidityAssembly,
    assemble_partial_institutional_projection,
)
from aip.product.configured.liquidity.sugef210_sight_approval_manifest import (
    read_approved_sight_manifest,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader

_MAX_JSON = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ConfiguredOpeningSession:
    cutoff: date
    scenario: str
    assembly: InstitutionalLiquidityAssembly
    sight_records_approved: int
    sight_source_sha256: str
    bank_support_sha256: str
    bank_document_sha256: str
    master_principal_events_approved: int = 0
    master_coupon_events_approved: int = 0
    master_coupon_ledger_sha256: str | None = None
    master_coupon_custodian_sha256: str | None = None
    master_source_sha256: str | None = None
    sight_added_by_currency: tuple[tuple[str, Decimal], ...] = ()
    xml_contractual_events_approved: int = 0
    contingent_scenario_events_approved: int = 0
    offbalance_commitments_reviewed: int = 0
    financial_plan_events_approved: int = 0
    financial_plan_source_sha256: str | None = None
    demand_deposit_accounts_reviewed: int = 0
    demand_deposit_runoff_events_approved: int = 0
    demand_deposit_source_sha256: str | None = None
    demand_deposit_native_reconciliations: tuple[tuple[str, str, str, int, Decimal], ...] = ()
    status: str = "PARTIAL_DOCUMENTED_OPENING_NOT_COMPLETE_FORECAST"


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate field in liquidity approval JSON")
        result[name] = value
    return result


def _json_document(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > _MAX_JSON:
        raise ValueError("Approval document missing or exceeds permitted size")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("Nonfinite JSON input is not permitted")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Approval document cannot be parsed") from exc
    if not isinstance(document, dict):
        raise ValueError("Approval document must be a JSON object")
    return document


def _required_text(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Required document field is missing: " + key)
    return value.strip()


def _original_amount(value: Any) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Bank opening amounts must be nonblank decimal strings")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid bank opening amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Bank opening balance must be finite and nonnegative")
    return amount


def _hash_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_configured_sight_opening(
    *,
    cutoff: date,
    scenario: str,
    approval_manifest: str | Path,
    bank_support_manifest: str | Path,
) -> ConfiguredOpeningSession:
    """Read the actual current-month XML and Master; no hard-coded bank balances.

    A bank-support JSON must name a separately retained, hashed bank or ICL
    document. Its stated balances remain signed-off *inputs*; this code cannot
    establish that the supporting document's figures were independently certified.
    The complete 365-day liquidity forecast therefore always remains PARTIAL.
    """
    approval_path = Path(approval_manifest)
    support_path = Path(bank_support_manifest)
    if approval_path.resolve() == support_path.resolve():
        raise ValueError("Approval and bank/ICL evidence require separate files")
    policy = _json_document(approval_path)
    support = _json_document(support_path)
    if _required_text(policy, "schema") != "SUGEF210_SIGHT_OPENING_V1":
        raise ValueError("Incorrect sight approval schema")
    if _required_text(support, "schema") != "SUGEF210_BANK_OPENING_V1":
        raise ValueError("Incorrect bank opening schema")
    if policy.get("cutoff") != cutoff.isoformat() or support.get("cutoff") != cutoff.isoformat():
        raise ValueError("Bank, XML approval and requested cutoff do not agree")
    if _required_text(support, "opening_reconciliation_reference") != _required_text(
        policy, "opening_reconciliation_reference"
    ):
        raise ValueError("Bank/ICL and sight manifest nonduplication approvals differ")
    accounts = policy.get("approved_account_codes")
    if (
        not isinstance(accounts, list)
        or not accounts
        or any(not isinstance(item, str) or not item.strip() for item in accounts)
    ):
        raise ValueError("Institutionally approved account codes are required")
    if len(set(accounts)) != len(accounts):
        raise ValueError("Duplicate sight account codes in approval")
    source_config = EnvironmentLoader().load_source_config()
    confia = source_config.xml_confia
    folder = source_config.folder_watch
    if not confia.enabled or not confia.root:
        raise ValueError("Institutional XML CONFIA source is not configured")
    if not folder.enabled:
        raise ValueError("Investment Master source is not configured for duplicate review")
    master_status, master_path, count = resolve_exact_cutoff_master(
        folder.portfolio_root, folder.portfolio_master_pattern, cutoff
    )
    if master_path is None or count != 1:
        raise ValueError("Exact-cutoff Master unavailable or ambiguous: " + master_status)
    master_source_hash = _hash_local(master_path)
    read = InstitutionalPortfolioMasterReader().read(
        master_path, valuation_date_override=cutoff, diagnostic_mode=False
    )
    if read.source_status != "HEALTHY" or not read.normalized_positions:
        raise ValueError("Investment Master cannot be used for duplicate review")
    if _hash_local(master_path) != master_source_hash:
        raise ValueError("Institutional Master changed while reading source positions")
    known_isins = frozenset(
        str(item.get("isin") or "").strip().upper()
        for item in read.normalized_positions
        if str(item.get("isin") or "").strip()
    )
    known_series = frozenset(
        str(item.get("series") or "").strip().upper()
        for item in read.normalized_positions
        if str(item.get("series") or "").strip()
    )
    reader = XMLConfiaMonthlySourceReader(confia.root)
    audited = audit_investment_current_accounts(
        reader=reader,
        cutoff=cutoff,
        policy=InvestmentCurrentAccountPolicy(
            approved_account_codes=frozenset(accounts),
            approval_reference=_required_text(policy, "account_classification_approval"),
        ),
        master_isins=known_isins,
        master_series=known_series,
        master_loaded=True,
    )
    if audited.invalid_source_principal or audited.missing_account_codes:
        raise ValueError("Source XML investment principal or accounting codes are incomplete")
    native = support.get("bank_opening_excluding_sight")
    certifications = support.get("opening_certifications")
    if not isinstance(native, dict) or not native or not isinstance(certifications, dict):
        raise ValueError("Bank opening and its independent attestations are required")
    if any(code not in {"CRC", "USD"} for code in native):
        raise ValueError("Unsupported bank opening currency")
    opening = {code: _original_amount(value) for code, value in native.items()}
    if any(
        not isinstance(certifications.get(code), str) or not certifications[code].strip()
        for code in ("CRC", "USD")
    ):
        raise ValueError("Both CRC and USD require bank/ICL source attestations")
    if set(opening) != {"CRC", "USD"}:
        raise ValueError("Both CRC and USD bank opening balances must be supplied")
    raw_support = Path(_required_text(support, "bank_or_icl_source_file"))
    if not raw_support.is_absolute() or not raw_support.is_file():
        raise ValueError("Original bank/ICL source document must exist locally")
    if raw_support.resolve() in {
        approval_path.resolve(),
        support_path.resolve(),
        master_path.resolve(),
    }:
        raise ValueError("Bank document must be independent of approvals and Master")
    expected_hash = _required_text(support, "bank_or_icl_source_sha256")
    bank_hash = _hash_local(raw_support)
    if len(expected_hash) != 64 or expected_hash.lower() != bank_hash:
        raise ValueError("Bank/ICL supporting document hash is inconsistent")
    verified = read_approved_sight_manifest(
        manifest_path=approval_path,
        cutoff=cutoff,
        source_audit=audited,
        bank_reconciled_opening=opening,
        opening_certifications=certifications,
    )
    reconciled_opening = dict(verified.opening_by_currency)
    admitted_master = None
    principal_reference = None
    source_principal = None
    master_nonduplication_refs: set[str] = set()
    principal_authorization = policy.get("master_principal_authorization")
    if principal_authorization is not None:
        if not isinstance(principal_authorization, dict):
            raise ValueError("Master principal authorization must be a structured record")
        actual_master_hash = master_source_hash
        if _required_text(principal_authorization, "master_sha256") != actual_master_hash:
            raise ValueError("Master principal approval no longer matches actual Master")
        principal_reference = _required_text(principal_authorization, "approval_reference")
        raw_principals = principal_authorization.get("approved_principal_records")
        if not isinstance(raw_principals, list) or not raw_principals:
            raise ValueError("Approved Master principal must list original individual events")
        source_principal = build_master_principal_evidence(
            cutoff=cutoff,
            master_sha256=actual_master_hash,
            positions=read.normalized_positions,
            principal_source_header=read.detected_column_mapping.get("principal_balance"),
            maturity_source_header=read.detected_column_mapping.get("maturity_date"),
        )
        approved = []
        for record in raw_principals:
            if not isinstance(record, dict):
                raise ValueError("Master principal approval row is not structured")
            try:
                settlement_date = date.fromisoformat(_required_text(record, "payment_date"))
            except ValueError as exc:
                raise ValueError("Invalid approved principal settlement date") from exc
            master_nonduplication_refs.add(_required_text(record, "nonduplication_reference"))
            approved.append(
                ApprovedMasterPrincipalPosition(
                    cashflow_reference=_required_text(record, "cashflow_reference"),
                    payment_date=settlement_date,
                    original_principal=_original_amount(record.get("original_principal")),
                    currency=_required_text(record, "currency"),
                    approval_reference=principal_reference,
                    settlement_availability_reference=_required_text(
                        record, "settlement_availability_reference"
                    ),
                    restriction_clearance_reference=_required_text(
                        record, "restriction_clearance_reference"
                    ),
                    nonduplication_reference=_required_text(record, "nonduplication_reference"),
                )
            )
        admitted_master = admit_approved_master_principal(
            source=source_principal,
            cutoff=cutoff,
            expected_master_sha256=actual_master_hash,
            records=approved,
        )
    xml_contractual = None
    single_contract_policy = policy.get("xml_contractual_schedule")
    partition_policies = policy.get("xml_contractual_schedules")
    if single_contract_policy is not None and partition_policies is not None:
        raise ValueError("Choose either a single contractual ledger or approved partitions")
    if partition_policies is not None:
        if not isinstance(partition_policies, list) or not (
            1 <= len(partition_policies) <= 32
        ):
            raise ValueError("Approved contractual partitions must contain 1 to 32 manifests")
        contract_policies = partition_policies
    elif single_contract_policy is not None:
        contract_policies = [single_contract_policy]
    else:
        contract_policies = []
    ledger_paths: set[Path] = set()
    nonduplication_references: set[str] = set()
    selected_schedules = []
    for contract_policy in contract_policies:
        if not isinstance(contract_policy, dict):
            raise ValueError("XML contractual schedule approval must be structured")
        ledger_path = Path(_required_text(contract_policy, "ledger_file"))
        if (
            not ledger_path.is_absolute()
            or ledger_path.resolve() in {
                approval_path.resolve(),
                support_path.resolve(),
                master_path.resolve(),
                raw_support.resolve(),
            }
            or ledger_path.resolve() in ledger_paths
        ):
            raise ValueError("Approved contractual ledgers must be independent original files")
        ledger_paths.add(ledger_path.resolve())
        nondup_ref = _required_text(contract_policy, "nonduplication_reference")
        if nondup_ref in nonduplication_references:
            raise ValueError("Duplicate contractual partition nonduplication reference")
        nonduplication_references.add(nondup_ref)
        xml_hashes = contract_policy.get("approved_xml_sha256")
        currency_codes = contract_policy.get("approved_currency_codes")
        term_codes = contract_policy.get("approved_term_deposit_codes", [])
        if not isinstance(xml_hashes, dict) or not isinstance(currency_codes, dict):
            raise ValueError("Dated XML source hashes and original currency mapping required")
        if not isinstance(term_codes, list) or any(
            not isinstance(code, str) for code in term_codes
        ):
            raise ValueError("Approved term-deposit account type codes must be a list")
        selected_schedules.append(
            import_approved_xml_contractual_payments(
                reader=reader,
                cutoff=cutoff,
                ledger_file=ledger_path,
                expected_ledger_sha256=_required_text(contract_policy, "ledger_sha256"),
                approved_xml_sha256=xml_hashes,
                approved_currency_codes=currency_codes,
                approved_term_deposit_codes=frozenset(term_codes),
                source_payment_approval=_required_text(
                    contract_policy, "source_payment_approval"
                ),
                settlement_approval=_required_text(contract_policy, "settlement_approval"),
                nonduplication_reference=nondup_ref,
            )
        )
    if selected_schedules:
        xml_contractual = merge_approved_xml_contractual_schedules(
            cutoff=cutoff, schedules=selected_schedules
        )
    offbalance = None
    contingent_policy = policy.get("offbalance_scenario")
    if contingent_policy is not None:
        if not isinstance(contingent_policy, dict):
            raise ValueError("Off-balance approvals must specify structured evidence")
        register_file = Path(_required_text(contingent_policy, "register_file"))
        policy_file = Path(_required_text(contingent_policy, "approval_file"))
        used_inputs = {
            approval_path.resolve(),
            support_path.resolve(),
            master_path.resolve(),
            raw_support.resolve(),
        }
        used_inputs.update(ledger_paths)
        if (
            not register_file.is_absolute()
            or not policy_file.is_absolute()
            or register_file.resolve() in used_inputs
            or policy_file.resolve() in used_inputs
            or register_file.resolve() == policy_file.resolve()
        ):
            raise ValueError("Off-balance register and approval must be independent source files")
        offbalance = read_governed_offbalance_scenario(
            cutoff=cutoff,
            scenario=scenario,
            source_csv=register_file,
            approval_json=policy_file,
            existing_contractual_source_refs=frozenset(
                event.reference
                for event in (xml_contractual.events if xml_contractual is not None else ())
            ),
            already_in_opening=frozenset(verified.included_source_references),
        )
    demand_runoff = None
    demand_policy = policy.get("demand_deposit_runoff")
    if demand_policy is not None:
        if not isinstance(demand_policy, dict):
            raise ValueError("Demand-deposit scenario authorization must be structured")
        demand_approval = Path(_required_text(demand_policy, "approval_file"))
        used_paths = {
            approval_path.resolve(),
            support_path.resolve(),
            master_path.resolve(),
            raw_support.resolve(),
        }
        used_paths.update(ledger_paths)
        if contingent_policy is not None:
            used_paths.add(register_file.resolve())
            used_paths.add(policy_file.resolve())
        if not demand_approval.is_absolute() or demand_approval.resolve() in used_paths:
            raise ValueError("Sight runoff approval must be independent of source files")
        fixed_deposits = frozenset(
            ordinal
            for key, ordinal in (
                xml_contractual.included_source_records if xml_contractual is not None else ()
            )
            if key == "CAPTACIONES"
        )
        demand_runoff = read_approved_demand_deposit_runoff(
            reader=reader,
            cutoff=cutoff,
            scenario=scenario,
            approval_file=demand_approval,
            contractually_scheduled_ordinals=fixed_deposits,
            already_in_opening=frozenset(verified.included_source_references),
        )
    approved_coupons = None
    coupon_policy = policy.get("investment_coupon_schedule")
    if coupon_policy is not None:
        if not isinstance(coupon_policy, dict):
            raise ValueError("Custodian coupon authorization must be structured")
        coupon_ledger = Path(_required_text(coupon_policy, "ledger_file"))
        coupon_approval = Path(_required_text(coupon_policy, "approval_file"))
        coupon_custody = Path(_required_text(coupon_policy, "custodian_document_file"))
        other_sources = {
            approval_path.resolve(),
            support_path.resolve(),
            master_path.resolve(),
            raw_support.resolve(),
        }
        other_sources.update(ledger_paths)
        if contingent_policy is not None:
            other_sources.update((register_file.resolve(), policy_file.resolve()))
        if demand_policy is not None:
            other_sources.add(demand_approval.resolve())
        coupon_paths = (coupon_ledger, coupon_approval, coupon_custody)
        if (
            any(not item.is_absolute() or item.resolve() in other_sources for item in coupon_paths)
            or len({item.resolve() for item in coupon_paths}) != 3
        ):
            raise ValueError("Coupon approval, ledger and custody must use independent files")
        master_hash = master_source_hash
        if source_principal is None:
            source_principal = build_master_principal_evidence(
                cutoff=cutoff,
                master_sha256=master_hash,
                positions=read.normalized_positions,
                principal_source_header=read.detected_column_mapping.get("principal_balance"),
                maturity_source_header=read.detected_column_mapping.get("maturity_date"),
            )
        prohibited_refs = set(master_nonduplication_refs)
        prohibited_refs.update(verified.included_source_references)
        if xml_contractual is not None:
            prohibited_refs.update(event.reference for event in xml_contractual.events)
            prohibited_refs.update(event.source for event in xml_contractual.events)
        prohibited_refs.update(nonduplication_references)
        approved_coupons = read_approved_master_coupons(
            source=source_principal,
            cutoff=cutoff,
            master_sha256=master_hash,
            ledger_file=coupon_ledger,
            approval_file=coupon_approval,
            custodian_document_file=coupon_custody,
            prohibited_nonduplication_refs=frozenset(prohibited_refs),
        )
    approved_scenarios = tuple(
        evidence
        for evidence in (
            offbalance.evidence if offbalance is not None else None,
            demand_runoff.evidence if demand_runoff is not None else None,
        )
        if evidence is not None
    )
    governed_scenario = None
    if approved_scenarios:
        governed_scenario = ScenarioGeneratedEvidence(
            cutoff=cutoff,
            scenario=scenario,
            flows=tuple(event for piece in approved_scenarios for event in piece.flows),
            assumptions=tuple(
                assumption for piece in approved_scenarios for assumption in piece.assumptions
            ),
            matched_exposure_count=sum(
                piece.matched_exposure_count for piece in approved_scenarios
            ),
        )
    approved_plan = None
    plan_policy = policy.get("financial_plan_scenario")
    if plan_policy is not None:
        if not isinstance(plan_policy, dict):
            raise ValueError("Financial plan authorization must be structured")
        plan_source = Path(_required_text(plan_policy, "source_file"))
        plan_approval = Path(_required_text(plan_policy, "approval_file"))
        used_paths = {
            approval_path.resolve(),
            support_path.resolve(),
            master_path.resolve(),
            raw_support.resolve(),
        }
        used_paths.update(ledger_paths)
        if contingent_policy is not None:
            used_paths.update((register_file.resolve(), policy_file.resolve()))
        if demand_policy is not None:
            used_paths.add(demand_approval.resolve())
        if coupon_policy is not None:
            used_paths.update(
                (coupon_ledger.resolve(), coupon_approval.resolve(), coupon_custody.resolve())
            )
        if (
            not plan_source.is_absolute()
            or not plan_approval.is_absolute()
            or plan_source.resolve() in used_paths
            or plan_approval.resolve() in used_paths
            or plan_source.resolve() == plan_approval.resolve()
        ):
            raise ValueError("Plan workbook and authorization must be independent source files")
        contractual_refs = set(master_nonduplication_refs)
        if approved_coupons is not None:
            contractual_refs.update(approved_coupons.nonduplication_references)
        if xml_contractual is not None:
            contractual_refs.update({event.reference for event in xml_contractual.events})
            contractual_refs.update({event.source for event in xml_contractual.events})
        contractual_refs.update(nonduplication_references)
        contractual_refs.update(verified.included_source_references)
        approved_plan = read_approved_financial_plan_overlay(
            source_file=plan_source,
            approval_file=plan_approval,
            cutoff=cutoff,
            scenario=scenario,
            existing_contractual_reconciliation_refs=frozenset(contractual_refs),
        )
    if _hash_local(master_path) != master_source_hash:
        raise ValueError("Institutional Master changed during liquidity reconciliation")
    assembly = assemble_partial_institutional_projection(
        cutoff=cutoff,
        scenario=scenario,
        master=admitted_master,
        master_maturity_recognition_reference=principal_reference,
        approved_xml_schedule=xml_contractual,
        approved_plan=approved_plan,
        approved_investment_coupons=approved_coupons,
        approved_behavioral=governed_scenario,
        verified_sight_opening=verified,
        opening_by_currency=reconciled_opening,
        opening_certifications=certifications,
        opening_nonduplication_reference=_required_text(
            support, "opening_reconciliation_reference"
        ),
    )
    if assembly.projection.certified_comprehensive:
        raise ValueError("Partial investment session cannot certify integral cashflows")
    expected_events = (
        (len(admitted_master.flows) if admitted_master is not None else 0)
        + (len(xml_contractual.events) if xml_contractual is not None else 0)
        + (len(offbalance.evidence.flows) if offbalance is not None else 0)
        + (len(demand_runoff.evidence.flows) if demand_runoff is not None else 0)
        + (len(approved_plan.events) if approved_plan is not None else 0)
        + (len(approved_coupons.events) if approved_coupons is not None else 0)
    )
    if assembly.projection.source_flow_count != expected_events:
        raise ValueError("Master and XML source payment events did not reconcile")
    return ConfiguredOpeningSession(
        cutoff=cutoff,
        scenario=scenario,
        assembly=assembly,
        sight_records_approved=verified.included_xml_accounts,
        sight_source_sha256=audited.xml_sha256,
        sight_added_by_currency=verified.added_by_currency,
        master_source_sha256=master_source_hash,
        bank_support_sha256=_hash_local(support_path),
        bank_document_sha256=bank_hash,
        master_principal_events_approved=(
            len(admitted_master.flows) if admitted_master is not None else 0
        ),
        master_coupon_events_approved=(
            len(approved_coupons.events) if approved_coupons is not None else 0
        ),
        master_coupon_ledger_sha256=(
            approved_coupons.ledger_sha256 if approved_coupons is not None else None
        ),
        master_coupon_custodian_sha256=(
            approved_coupons.custodian_sha256 if approved_coupons is not None else None
        ),
        xml_contractual_events_approved=(
            len(xml_contractual.events) if xml_contractual is not None else 0
        ),
        contingent_scenario_events_approved=(
            len(offbalance.evidence.flows) if offbalance is not None else 0
        ),
        offbalance_commitments_reviewed=(
            offbalance.commitments_checked if offbalance is not None else 0
        ),
        financial_plan_events_approved=(
            len(approved_plan.events) if approved_plan is not None else 0
        ),
        financial_plan_source_sha256=(
            approved_plan.source_sha256 if approved_plan is not None else None
        ),
        demand_deposit_accounts_reviewed=(
            demand_runoff.approved_accounts_seen if demand_runoff is not None else 0
        ),
        demand_deposit_runoff_events_approved=(
            len(demand_runoff.evidence.flows) if demand_runoff is not None else 0
        ),
        demand_deposit_source_sha256=(
            demand_runoff.xml_sha256 if demand_runoff is not None else None
        ),
        demand_deposit_native_reconciliations=(
            demand_runoff.reconciled_native_groups if demand_runoff is not None else ()
        ),
    )
