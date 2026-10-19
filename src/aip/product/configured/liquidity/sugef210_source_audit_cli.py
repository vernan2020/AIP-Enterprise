"""Institutional SUGEF 2-10 liquidity source inventory, no demo or writes."""

from __future__ import annotations

import argparse
import json
from datetime import date

from aip.product.configured.irrbb.investment_master_discovery import (
    resolve_exact_cutoff_master,
)
from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.configured.liquidity.investment_current_account_xml_audit import (
    InvestmentCurrentAccountPolicy,
    audit_investment_current_accounts,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def inspect_xml_investment_source(cutoff: date) -> dict[str, object]:
    config = EnvironmentLoader().load_source_config()
    confia = config.xml_confia
    if not confia.enabled or not confia.root:
        return {"status": "BLOCKED_XML_CONFIA_UNCONFIGURED", "cutoff": cutoff.isoformat()}

    master_status = "MASTER_NOT_CONFIGURED"
    master_isins: frozenset[str] = frozenset()
    master_series: frozenset[str] = frozenset()
    master_position_count: int | None = None
    folder = config.folder_watch
    if folder.enabled:
        status, master_path, count = resolve_exact_cutoff_master(
            folder.portfolio_root, folder.portfolio_master_pattern, cutoff
        )
        master_status = status
        if master_path is not None and count == 1:
            read = InstitutionalPortfolioMasterReader().read(
                master_path, valuation_date_override=cutoff, diagnostic_mode=False
            )
            if read.source_status != "HEALTHY":
                raise ValueError("Master cannot be used for duplicate review")
            master_isins = frozenset(
                str(item.get("isin") or "").strip().upper()
                for item in read.normalized_positions
                if str(item.get("isin") or "").strip()
            )
            master_series = frozenset(
                str(item.get("series") or "").strip().upper()
                for item in read.normalized_positions
                if str(item.get("series") or "").strip()
            )
            master_position_count = len(read.normalized_positions)
            master_status = "MASTER_EXACT_CUTOFF_READ"

    audit = audit_investment_current_accounts(
        reader=XMLConfiaMonthlySourceReader(confia.root),
        cutoff=cutoff,
        policy=InvestmentCurrentAccountPolicy(
            approved_account_codes=frozenset(),
            approval_reference="",
        ),
        master_isins=master_isins,
        master_series=master_series,
        master_loaded=master_position_count is not None,
    )
    return {
        "status": audit.status,
        "cutoff": cutoff.isoformat(),
        "xml_month": audit.xml_month.isoformat(),
        "xml_source": audit.xml_filename,
        "entity_id": audit.entity_id,
        "sha256": audit.xml_sha256,
        "master_review_status": master_status,
        "master_isin_references": len(master_isins),
        "master_positions_read": master_position_count,
        "master_series_references": len(master_series),
        "repeated_source_record_ids": audit.repeated_record_ids,
        "xml_records_read": audit.records_read,
        "invalid_source_principal": audit.invalid_source_principal,
        "missing_account_codes": audit.missing_account_codes,
        "accounts": [
            {
                "account_code": g.account_code,
                "currency_source_code": g.currency_source_code,
                "record_count": g.record_count,
                "source_principal": str(g.principal),
                "classification": g.classification,
                "master_isin_matches": g.master_identifier_matches,
                "unverified_master_overlap": g.unverified_master_overlap,
            }
            for g in audit.groups
        ],
        "record_evidence": [
            {
                "source_reference": row.source_reference,
                "raw_record_id": row.raw_record_id,
                "record_ordinal": row.record_ordinal,
                "action": row.action,
                "account_code": row.account_code,
                "currency_source_code": row.currency_source_code,
                "source_principal_raw": row.raw_principal,
                "source_principal": str(row.principal) if row.principal is not None else None,
                "instrument_id": row.instrument_id,
                "isin": row.isin,
                "series": row.series,
                "classification": row.classification,
                "master_reconciliation": row.master_reconciliation,
                "withdrawable_amount": None,
            }
            for row in audit.records
        ],
        "current_account_cash_usable_today": None,
        "liquidity_projection_ready": False,
        "next_steps": (
            "Classify sight-investment accounts through approved accounting codes",
            "Reconcile distinct positions with Master and account balances",
            "Confirm withdrawability, settlement date and any restrictions",
            "Only then add validated available balances to opening liquidity",
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIP Liquidez SUGEF 2-10 real-source audit")
    parser.add_argument("--cutoff", required=True)
    parsed = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(parsed.cutoff)
    except ValueError:
        parser.error("--cutoff debe tener formato YYYY-MM-DD")
    try:
        result = inspect_xml_investment_source(cutoff)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {
            "status": "BLOCKED_SOURCE_READ",
            "error_type": type(exc).__name__,
            "cutoff": cutoff.isoformat(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
