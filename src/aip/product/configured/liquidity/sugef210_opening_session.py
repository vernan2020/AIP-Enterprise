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

from aip.product.configured.irrbb.investment_master_discovery import (
    resolve_exact_cutoff_master,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
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
    xml_contractual_events_approved: int = 0
    contingent_scenario_events_approved: int = 0
    offbalance_commitments_reviewed: int = 0
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
    read = InstitutionalPortfolioMasterReader().read(
        master_path, valuation_date_override=cutoff, diagnostic_mode=False
    )
    if read.source_status != "HEALTHY" or not read.normalized_positions:
        raise ValueError("Investment Master cannot be used for duplicate review")
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
    principal_authorization = policy.get("master_principal_authorization")
    if principal_authorization is not None:
        if not isinstance(principal_authorization, dict):
            raise ValueError("Master principal authorization must be a structured record")
        actual_master_hash = _hash_local(master_path)
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
    contract_policy = policy.get("xml_contractual_schedule")
    if contract_policy is not None:
        if not isinstance(contract_policy, dict):
            raise ValueError("XML contractual schedule approval must be structured")
        ledger_path = Path(_required_text(contract_policy, "ledger_file"))
        if not ledger_path.is_absolute() or ledger_path.resolve() in {
            approval_path.resolve(),
            support_path.resolve(),
            master_path.resolve(),
            raw_support.resolve(),
        }:
            raise ValueError("Original dated payment ledger must be independent of source inputs")
        xml_hashes = contract_policy.get("approved_xml_sha256")
        currency_codes = contract_policy.get("approved_currency_codes")
        term_codes = contract_policy.get("approved_term_deposit_codes", [])
        if not isinstance(xml_hashes, dict) or not isinstance(currency_codes, dict):
            raise ValueError("Dated XML source hashes and original currency mapping required")
        if not isinstance(term_codes, list) or any(
            not isinstance(code, str) for code in term_codes
        ):
            raise ValueError("Approved term-deposit account type codes must be a list")
        xml_contractual = import_approved_xml_contractual_payments(
            reader=reader,
            cutoff=cutoff,
            ledger_file=ledger_path,
            expected_ledger_sha256=_required_text(contract_policy, "ledger_sha256"),
            approved_xml_sha256=xml_hashes,
            approved_currency_codes=currency_codes,
            approved_term_deposit_codes=frozenset(term_codes),
            source_payment_approval=_required_text(contract_policy, "source_payment_approval"),
            settlement_approval=_required_text(contract_policy, "settlement_approval"),
            nonduplication_reference=_required_text(contract_policy, "nonduplication_reference"),
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
        if contract_policy is not None:
            used_inputs.add(ledger_path.resolve())
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
    assembly = assemble_partial_institutional_projection(
        cutoff=cutoff,
        scenario=scenario,
        master=admitted_master,
        master_maturity_recognition_reference=principal_reference,
        approved_xml_schedule=xml_contractual,
        approved_behavioral=offbalance.evidence if offbalance is not None else None,
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
    )
    if assembly.projection.source_flow_count != expected_events:
        raise ValueError("Master and XML source payment events did not reconcile")
    return ConfiguredOpeningSession(
        cutoff=cutoff,
        scenario=scenario,
        assembly=assembly,
        sight_records_approved=verified.included_xml_accounts,
        sight_source_sha256=audited.xml_sha256,
        bank_support_sha256=_hash_local(support_path),
        bank_document_sha256=bank_hash,
        master_principal_events_approved=(
            len(admitted_master.flows) if admitted_master is not None else 0
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
    )
