"""Operational CONFIGURED preflight for real SUGEF210 preview, no institutional writes.

Never replaces missing contractual sources with simulated values. Without separate
approvals this only confirms that the XML/Master can be inspected. With both
original authorization manifests, execute the actual opening and partial ladder.
No private paths, source balances, credentials or document names are returned.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from aip.product.configured.liquidity.sugef210_opening_session import (
    run_configured_sight_opening,
)
from aip.product.configured.liquidity.sugef210_source_audit_cli import (
    inspect_xml_investment_source,
)

_EXPECTED_SOURCE_STATUS = "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH"
_REQUIRED_MASTER_STATUS = "MASTER_EXACT_CUTOFF_READ"


def evaluate_readiness(
    *,
    cutoff: date,
    scenario: str,
    approval: str | Path | None = None,
    bank: str | Path | None = None,
) -> dict[str, Any]:
    """Return a source-backed operational gate, deliberately not a certification."""
    if os.environ.get("AIP_EXECUTION_MODE", "").upper() != "CONFIGURED" or os.environ.get(
        "AIP_DEMO_MODE_ENABLED", ""
    ).lower() not in {"false", "0"}:
        return {
            "status": "BLOCKED_NOT_CONFIGURED",
            "cutoff": cutoff.isoformat(),
            "real_sources_only": True,
        }
    if scenario not in {"BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED"}:
        return {"status": "BLOCKED_SCENARIO", "cutoff": cutoff.isoformat()}

    inventory = inspect_xml_investment_source(cutoff)
    status = str(inventory.get("status") or "BLOCKED_SOURCE_READ")
    master = str(inventory.get("master_review_status") or "N/D")
    basic: dict[str, Any] = {
        "status": "BLOCKED_SOURCE_INVENTORY",
        "cutoff": cutoff.isoformat(),
        "scenario": scenario,
        "mode": "CONFIGURED",
        "real_sources_only": True,
        "xml_inventory_status": status,
        "master_review_status": master,
        "xml_records_read": inventory.get("xml_records_read"),
        "master_positions_read": inventory.get("master_positions_read"),
        "projection_regulatorily_certified": False,
    }
    if status != _EXPECTED_SOURCE_STATUS:
        return basic
    if master != _REQUIRED_MASTER_STATUS:
        basic["status"] = "BLOCKED_MASTER_AT_CUTOFF"
        return basic
    if (approval is None) != (bank is None):
        basic["status"] = "BLOCKED_APPROVAL_PAIR_REQUIRED"
        return basic
    if approval is None:
        basic["status"] = "SOURCE_READY_APPROVALS_REQUIRED"
        basic["next_action"] = (
            "Provide separately approved sight/investment and bank/ICL JSON files; "
            "no cashflows were recognized by this read-only source preflight."
        )
        return basic

    session = run_configured_sight_opening(
        cutoff=cutoff,
        scenario=scenario,
        approval_manifest=approval,
        bank_support_manifest=bank,
    )
    projection = session.assembly.projection
    if (
        len(projection.windows) != 17
        or len(projection.rows) != 34
        or projection.certified_comprehensive
        or len(session.assembly.audited_events) != projection.source_flow_count
    ):
        raise ValueError("SUGEF210 operational projection violates validated partial contract")

    basic["status"] = (
        "PARTIAL_GOVERNED_PROJECTION"
        if projection.source_flow_count
        else "PARTIAL_OPENING_ONLY_NO_FUTURE_FLOWS"
    )
    basic["projection_status"] = projection.status
    basic["projection_rows"] = len(projection.rows)
    basic["band_count"] = len(projection.windows)
    basic["approved_source_events"] = projection.source_flow_count
    basic["audited_individual_events"] = len(session.assembly.audited_events)
    basic["events_after_365_days"] = projection.excluded_out_of_horizon
    basic["opening_supported_currencies"] = sorted(
        {row.currency for row in projection.rows if row.opening_liquidity is not None}
    )
    basic["source_reconciliations"] = [
        {
            "group": source.source_name,
            "currency": source.currency,
            "count_in_365_days": source.events_inside_horizon,
            "count_after_365_days": source.events_after_horizon,
            "coverage": source.status,
        }
        for source in session.assembly.source_reconciliations
    ]
    basic["missing_evidence"] = list(session.assembly.missing_institutional_evidence)
    return basic


def verify_runtime_without_institutional_data() -> dict[str, Any]:
    """Smoke the installed GUI and its 17 windows without touching configured sources."""
    from aip.domain.liquidity.cashflow.services.sugef210_projection import (
        sugef210_windows,
    )

    # Called from a dedicated CMD process, never from inside the live desktop.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QTabWidget

    from aip.ui.modules.liquidity.views.sugef210_projection_panel import (
        SUGEF210ProjectionPanel,
    )

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    panel: SUGEF210ProjectionPanel | None = None
    try:
        panel = SUGEF210ProjectionPanel()
        windows = sugef210_windows(panel._cutoff)
        if len(windows) != 17 or panel._windows.rowCount() != 17:
            raise ValueError("Liquidity band definitions are not ready")
        tabs = panel.findChildren(QTabWidget)
        names = {tab.tabText(index) for tab in tabs for index in range(tab.count())}
        required = {
            "Conciliación inversiones",
            "Trazabilidad por operación",
            "Conciliación captaciones vista",
        }
        if not required.issubset(names):
            raise ValueError("Required SUGEF210 reconciliation tabs unavailable")
        if panel._governed_projection is not None:
            raise ValueError("Runtime test must not populate institutional cashflows")
        if any(label.text() != "N/D" for label in panel._projected_kpis.values()):
            raise ValueError("Runtime test must not populate liquidity KPIs")
        return {
            "status": "RUNTIME_SELFTEST_OK",
            "execution_mode": "CONFIGURED",
            "source_cutoff_evaluated": False,
            "institutional_files_read": False,
            "projection_regulatorily_certified": False,
            "window_count": len(windows),
            "expected_currency_rows": 34,
            "reconciliation_tabs_available": True,
            "native_currencies": ["CRC", "USD"],
        }
    finally:
        if panel is not None:
            panel.close()
        if created_app:
            app.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AIP PREVIEW CONFIGURED: real XML/Master preflight and governed SUGEF210"
    )
    parser.add_argument("--cutoff", help="YYYY-MM-DD")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate installed Qt GUI and 17 SUGEF210 bands without institutional sources",
    )
    parser.add_argument(
        "--scenario",
        choices=("BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED"),
        default="BASE",
    )
    parser.add_argument("--approval")
    parser.add_argument("--bank")
    args = parser.parse_args(argv)
    if args.self_test:
        if args.cutoff or args.approval or args.bank:
            parser.error("--self-test cannot be combined with institutional source arguments")
        if (
            os.environ.get("AIP_EXECUTION_MODE", "").upper() != "CONFIGURED"
            or os.environ.get("AIP_DEMO_MODE_ENABLED", "").lower() not in {"false", "0"}
        ):
            outcome = {
                "status": "BLOCKED_NOT_CONFIGURED",
                "private_paths_and_values_redacted": True,
            }
        else:
            try:
                outcome = verify_runtime_without_institutional_data()
            except Exception as exc:
                outcome = {
                    "status": "BLOCKED_RUNTIME_SELFTEST",
                    "error_type": type(exc).__name__,
                    "private_paths_and_values_redacted": True,
                }
    else:
        if args.cutoff is None:
            parser.error("--cutoff is required unless --self-test is selected")
        try:
            cutoff = date.fromisoformat(args.cutoff)
        except ValueError:
            parser.error("--cutoff must use YYYY-MM-DD")
        try:
            outcome = evaluate_readiness(
                cutoff=cutoff,
                scenario=args.scenario,
                approval=args.approval,
                bank=args.bank,
            )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            outcome = {
                "status": "BLOCKED_INSTITUTIONAL_EVIDENCE",
                "cutoff": cutoff.isoformat(),
                "scenario": args.scenario,
                "error_type": type(exc).__name__,
                "private_paths_and_values_redacted": True,
            }
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 2 if str(outcome["status"]).startswith("BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
