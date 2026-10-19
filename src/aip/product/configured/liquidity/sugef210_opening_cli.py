"""CMD diagnostic for approved SUGEF210 opening, native-currency source cash events."""

from __future__ import annotations

import argparse
import json
from datetime import date

from aip.product.configured.liquidity.sugef210_opening_session import (
    ConfiguredOpeningSession,
    run_configured_sight_opening,
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
        "source_flows_included": result.source_flow_count,
        "not_a_regulatory_cashflow_certification": True,
        "missing_areas": list(result.missing_source_areas),
        "missing_evidence": list(session.assembly.missing_institutional_evidence),
        "windows": [
            {
                "currency": row.currency,
                "band": row.window.key,
                "start": row.window.start.isoformat(),
                "end": row.window.end.isoformat(),
                "documented_event_count": row.event_count,
                "cash_inflow_asset": str(row.asset_inflows) if row.event_count else None,
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
