"""CMD diagnostic for approved SUGEF210 opening, native-currency source cash events."""

from __future__ import annotations

import argparse
import json
from datetime import date

from aip.product.configured.liquidity.sugef210_opening_session import (
    ConfiguredOpeningSession,
    run_configured_sight_opening,
)
from aip.product.configured.liquidity.sugef210_reconciliation_summary import (
    summarize_approved_contractual_source_coverage,
)


def summarize_session(session: ConfiguredOpeningSession) -> dict[str, object]:
    """Display only audited amounts and partial evidence, never secrets/paths."""
    result = session.assembly.projection
    if result.certified_comprehensive:
        raise ValueError("Sight-only runner cannot certify comprehensive liquidity")
    return {
        "status": session.status,
        "cutoff": session.cutoff.isoformat(),
        "scenario": session.scenario,
        "xml_sha256": session.sight_source_sha256,
        "bank_support_sha256": session.bank_support_sha256,
        "bank_document_sha256": session.bank_document_sha256,
        "sight_accounts_verified": session.sight_records_approved,
        "master_principal_events_approved": session.master_principal_events_approved,
        "master_coupon_events_approved": session.master_coupon_events_approved,
        "master_coupon_ledger_sha256": session.master_coupon_ledger_sha256,
        "master_coupon_custodian_sha256": session.master_coupon_custodian_sha256,
        "master_source_sha256": session.master_source_sha256,
        "sight_added_by_currency": {
            currency: str(amount) for currency, amount in session.sight_added_by_currency
        },
        "credit_deposits_borrowing_payment_events_approved": (
            session.xml_contractual_events_approved
        ),
        "contractual_xml_selected_contracts_by_source": list(
            summarize_approved_contractual_source_coverage(session.xml_contractual_source_coverage)
        ),
        "offbalance_commitments_reviewed": session.offbalance_commitments_reviewed,
        "governed_offbalance_scenario_events": (session.contingent_scenario_events_approved),
        "financial_plan_events_approved": session.financial_plan_events_approved,
        "financial_plan_source_sha256": session.financial_plan_source_sha256,
        "demand_deposit_accounts_reviewed": session.demand_deposit_accounts_reviewed,
        "demand_deposit_runoff_events_approved": (session.demand_deposit_runoff_events_approved),
        "demand_deposit_xml_sha256": session.demand_deposit_source_sha256,
        "demand_deposit_reconciled_source_groups": [
            {
                "account_code": account,
                "type_code": source_type,
                "original_currency_code": currency_code,
                "source_record_count": count,
                "original_native_balance": str(balance),
            }
            for account, source_type, currency_code, count, balance in session.demand_deposit_native_reconciliations
        ],
        "source_flows_included": result.source_flow_count,
        "individual_events_reconciled": len(session.assembly.audited_events),
        "events_after_365_days_reconciled": sum(
            event.horizon_status == "AFTER_365D" for event in session.assembly.audited_events
        ),
        "not_a_regulatory_cashflow_certification": True,
        "document_hash_is_not_a_bank_signature": True,
        "projection_status": result.status,
        "missing_areas": list(result.missing_source_areas),
        "missing_evidence": list(session.assembly.missing_institutional_evidence),
        "reconciliation_by_source_and_currency": [
            {
                "source": item.source_name,
                "currency": item.currency,
                "events_received": item.received_events,
                "events_within_365_days": item.events_inside_horizon,
                "events_after_365_days": item.events_after_horizon,
                "native_amount_within_365_days": str(item.principal_or_flow_total_inside_horizon),
                "status": item.status,
            }
            for item in session.assembly.source_reconciliations
        ],
        "windows": [
            {
                "currency": row.currency,
                "band": row.window.key,
                "start": row.window.start.isoformat(),
                "end": row.window.end.isoformat(),
                "documented_event_count": row.event_count,
                "cash_inflow_asset": str(row.asset_inflows) if row.event_count else None,
                "cash_outflow_liability": (
                    str(row.liability_outflows) if row.event_count else None
                ),
                "cash_inflow_liability": (str(row.liability_inflows) if row.event_count else None),
                "cash_outflow_asset": (str(row.asset_outflows) if row.event_count else None),
                "offbalance_cash_outflow_partial": (
                    str(row.off_balance_outflows) if row.event_count else None
                ),
                "offbalance_cash_inflow_partial": (
                    str(row.off_balance_inflows) if row.event_count else None
                ),
                "net_documented": str(row.net_flow) if row.event_count else None,
                "opening": (
                    str(row.opening_liquidity) if row.opening_liquidity is not None else None
                ),
                "balance_partial": (
                    str(row.projected_liquidity) if row.projected_liquidity is not None else None
                ),
                "funding_need_partial": (
                    str(row.financing_need) if row.financing_need is not None else None
                ),
            }
            for row in result.rows
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Solo AIP CONFIGURED: XML CONFIA, Maestro y caja aprobada; sin DEMO"
    )
    parser.add_argument("--cutoff", required=True)
    parser.add_argument(
        "--scenario",
        default="BASE",
        choices=("BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED"),
    )
    parser.add_argument("--approval", required=True)
    parser.add_argument("--bank", required=True)
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("Fecha de corte inválida, use YYYY-MM-DD")
    try:
        session = run_configured_sight_opening(
            cutoff=cutoff,
            scenario=args.scenario,
            approval_manifest=args.approval,
            bank_support_manifest=args.bank,
        )
        report = summarize_session(session)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_INSTITUTIONAL_EVIDENCE",
                    "cutoff": cutoff.isoformat(),
                    "scenario": args.scenario,
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
