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

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader
from aip.product.configured.liquidity.sugef210_obligation_identity_audit import (
    audit_obligation_maturity_identity,
)
from aip.product.configured.liquidity.sugef210_opening_session import (
    run_configured_sight_opening,
)
from aip.product.configured.liquidity.sugef210_source_audit_cli import (
    inspect_xml_investment_source,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader

_EXPECTED_SOURCE_STATUS = "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH"
_REQUIRED_MASTER_STATUS = "MASTER_EXACT_CUTOFF_READ"

# Keep the native source layout visible, without declaring balances to be cashflows.
_CONTRACTUAL_SOURCE_ACTIONS = {
    "CREDIT": (
        "XML_CARTERA_PAGOS",
        "Conciliar cronograma individual completo de principal e intereses de cartera "
        "contra el XML; aportar fechas, montos y autorizaciones independientes.",
    ),
    "CAPTACIONES": (
        "XML_CAPTACIONES_PAGOS",
        "Separar captación a plazo y a la vista por código original aprobado; "
        "conciliar pagos contractuales y supuestos de retiros conductuales.",
    ),
    "BORROWING": (
        "XML_OBLIGACIONES_PAGOS",
        "Conciliar cronograma de principal e intereses de obligaciones con sus "
        "fechas de pago y respaldos originales.",
    ),
    "BORROWING_MATURITY": (
        "XML_OBLIGACIONES_BANDAS",
        "Contrastar el bandeo regulatorio con el detalle de obligaciones; "
        "los saldos agregados por tramo no generan pagos fechados.",
    ),
}


def build_contractual_source_gates(source_inventory: object) -> list[dict[str, str]]:
    """Show source-specific execution gaps; no native balances or private paths leak.

    The existing XML inspector already reads these source files. Their dates and
    accounting balances only establish coverage, never payment settlement amounts.
    """
    raw_rows = source_inventory if isinstance(source_inventory, (list, tuple)) else ()
    indexed: dict[str, dict[str, object]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        key = row.get("source_key")
        if isinstance(key, str) and key in _CONTRACTUAL_SOURCE_ACTIONS:
            if key in indexed:
                raise ValueError("Repeated source perimeter in CONFIA inventory")
            indexed[key] = row

    result: list[dict[str, str]] = []
    for key, (check, action) in _CONTRACTUAL_SOURCE_ACTIONS.items():
        row = indexed.get(key)
        if row is None:
            state = "NOT_INSPECTED"
            detail = "Inventario contractual no disponible en esta verificación."
        elif row.get("status") == "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO":
            state = "BLOCKED"
            detail = "XML original del corte no localizado; no asumir saldo cero."
        elif key == "BORROWING_MATURITY" and row.get("status") in {
            "AGGREGATE_SOURCE_FIELD_MAP_REVIEW_REQUIRED",
            "AGGREGATE_SOURCE_REFERENCE_NOT_CASHFLOWS",
        }:
            count = row.get("records")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("Invalid aggregated obligation source record count")
            absent = row.get("unmapped_source_fields")
            unmapped = [
                field
                for field in (absent if isinstance(absent, list) else ())
                if isinstance(field, str) and field.strip()
            ]
            if row.get("status") == "AGGREGATE_SOURCE_FIELD_MAP_REVIEW_REQUIRED":
                state = "SCHEMA_REVIEW"
                detail = (
                    f"{count} registros de bandeo; etiquetas sin correspondencia: "
                    f"{', '.join(unmapped) or 'por inspeccionar'}. "
                    "La ausencia de etiquetas a nivel de archivo no equivale a "
                    "incidencias de saldos por cada registro. "
                )
            else:
                state = "REFERENCE_ONLY"
                detail = (
                    f"{count} registros de bandeo revisados. "
                    "La fuente agregada no es un calendario de liquidación. "
                )
        elif row.get("status") != "SOURCE_FIELDS_INSPECTED_NOT_A_PAYMENT_SCHEDULE":
            state = "BLOCKED"
            detail = "El estado del XML contractual no permite evaluar cobertura."
        else:
            count = row.get("records")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("Invalid contractual source record count")
            invalid = sum(
                value
                for field in (
                    "missing_balance",
                    "invalid_balance",
                    "missing_currency",
                    "missing_account",
                )
                for value in (row.get(field),)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            )
            date_defects = 0
            date_fields = row.get("dates")
            if isinstance(date_fields, list):
                for field in date_fields:
                    if not isinstance(field, dict):
                        continue
                    for label in ("missing", "invalid"):
                        value = field.get(label)
                        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                            date_defects += value
            state = "SOURCE_ONLY" if count else "EMPTY_REVIEW"
            detail = (
                f"{count} registros; {invalid} incidencias de campos básicos; "
                f"{date_defects} fechas ausentes o inválidas. "
                "No hay cronograma de cobros/pagos individual aprobado. "
            )
        result.append({"check": check, "state": state, "next_action": detail + " " + action})
    return result


def build_operational_gates(
    *,
    xml_status: str,
    master_status: str,
    approvals_provided: bool,
    projection_executed: bool = False,
    approval_failed: bool = False,
    contractual_inventory: object = None,
) -> list[dict[str, str]]:
    """Explain the next real-source blockers without exposing institutional data."""
    if approval_failed and projection_executed:
        raise ValueError("Rejected authorization cannot certify a completed projection")
    xml_ready = xml_status == _EXPECTED_SOURCE_STATUS
    master_ready = master_status == _REQUIRED_MASTER_STATUS
    xml_pending = xml_status == "NOT_INSPECTED"
    master_pending = master_status == "NOT_INSPECTED"
    gates = [
        {
            "check": "XML_CONFIA_CORTE",
            "state": "PENDING" if xml_pending else "READY" if xml_ready else "BLOCKED",
            "next_action": (
                "Inspeccionar XML CONFÍA del corte seleccionado."
                if xml_pending
                else (
                    "Fuente XML del corte localizada; saldos a la vista no certificados."
                    if xml_ready
                    else "Verificar configuración XML CONFÍA y archivos originales del corte."
                )
            ),
        },
        {
            "check": "MAESTRO_INVERSIONES_CORTE",
            "state": "PENDING" if master_pending else "READY" if master_ready else "BLOCKED",
            "next_action": (
                "Inspeccionar Maestro de inversiones del corte seleccionado."
                if master_pending
                else (
                    "Maestro original del corte disponible para conciliación."
                    if master_ready
                    else "Localizar exactamente un Maestro del mismo corte y validar su lectura."
                )
            ),
        },
        {
            "check": "AUTORIZACION_Y_CONCILIACION_ICL",
            "state": (
                "BLOCKED"
                if approval_failed
                else (
                    "VALIDATED"
                    if projection_executed
                    else "PENDING_VALIDATION" if approvals_provided else "REQUIRED"
                )
            ),
            "next_action": (
                "Apertura rechazada: corregir autorización y conciliación originales del corte."
                if approval_failed
                else (
                    "Documentos originales verificados según los controles de la sesión."
                    if projection_executed
                    else (
                        "Validar ambos documentos independientes en la misma sesión."
                        if approvals_provided
                        else "Seleccionar autorización institucional y conciliación bancaria/ICL."
                    )
                )
            ),
        },
        {
            "check": "PERIMETRO_CONTRACTUAL_INTEGRAL",
            "state": "PARTIAL" if projection_executed else "NOT_EVALUATED",
            "next_action": (
                "Conciliar las fuentes y operaciones todavía excluidas antes de certificar."
                if projection_executed
                else "No reconocer cobros/pagos futuros sin fechas y aprobaciones específicas."
            ),
        },
    ]
    if contractual_inventory is not None:
        gates.extend(build_contractual_source_gates(contractual_inventory))
    return gates


def inspect_obligation_identity_with_config(cutoff: date) -> dict[str, Any]:
    """Run opt-in read-only reference matching with existing private source config."""
    config = EnvironmentLoader().load_source_config()
    if not config.xml_confia.enabled or not config.xml_confia.root:
        return {
            "status": "BLOCKED_XML_CONFIA_UNCONFIGURED",
            "cashflows_recognized": 0,
        }
    reader = XMLConfiaMonthlySourceReader(config.xml_confia.root)
    return audit_obligation_maturity_identity(reader=reader, cutoff=cutoff)


def evaluate_readiness(
    *,
    cutoff: date,
    scenario: str,
    approval: str | Path | None = None,
    bank: str | Path | None = None,
    identity_linkage: bool = False,
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
        "operational_gates": build_operational_gates(
            xml_status=status,
            master_status=master,
            approvals_provided=approval is not None and bank is not None,
            contractual_inventory=inventory.get("contractual_source_inventory"),
        ),
    }
    if identity_linkage:
        linkage = inspect_obligation_identity_with_config(cutoff)
        basic["obligation_identity_linkage"] = linkage
        matches = linkage.get("unique_maturity_rows_matched", 0)
        issue = str(linkage.get("status") or "N/D")
        basic["operational_gates"].append(
            {
                "check": "XML_OBLIGACIONES_VINCULACION",
                "state": (
                    "REFERENCE_ONLY" if issue == "MATCHED_REFERENCE_ONLY" else "REVIEW_REQUIRED"
                ),
                "next_action": (
                    f"Coincidencias únicas por clave compuesta: {matches}. "
                    "Revisar registros ambiguos/no vinculados y validar catálogo de rangos "
                    "y cronogramas contractuales; no se reconocen flujos."
                ),
            }
        )
        principal = linkage.get("principal_reconciliation")
        if isinstance(principal, dict):
            exact = principal.get("distinct_contracts_reconciled_exactly", 0)
            different = principal.get("distinct_contracts_with_principal_difference", 0)
            unusable_contract = principal.get(
                "matched_contracts_without_usable_source_principal", 0
            )
            unusable_bands = principal.get(
                "matched_contracts_without_usable_band_principal", 0
            )
            unbanded = linkage.get("contract_identities_without_maturity_bands_by_source")
            remaining = sum(
                value
                for value in (unbanded.values() if isinstance(unbanded, dict) else ())
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            )
            basic["operational_gates"].append(
                {
                    "check": "XML_OBLIGACIONES_CONCILIACION_PRINCIPAL",
                    "state": (
                        "REFERENCE_RECONCILED"
                        if not (different or unusable_contract or unusable_bands)
                        and exact > 0 and issue == "MATCHED_REFERENCE_ONLY"
                        else "REVIEW_REQUIRED"
                    ),
                    "next_action": (
                        f"Contratos conciliados exactamente: {exact}; diferencias: {different}; "
                        f"principal contractual inválido: {unusable_contract}; "
                        f"principal bandeado inválido: {unusable_bands}; "
                        f"operaciones sin bandeo: {remaining}. "
                        "No asignar fechas ni retiros sin la metodología y evidencia aprobadas."
                    ),
                }
            )
    for perimeter in inventory.get("contractual_source_inventory") or ():
        if isinstance(perimeter, dict) and perimeter.get("source_key") == "BORROWING_MATURITY":
            basic["aggregate_obligation_xml_schema"] = {
                "status": perimeter.get("status"),
                "records": perimeter.get("records"),
                "expected_tags_not_observed": perimeter.get("unmapped_source_fields", []),
                "observed_tag_names_only": perimeter.get("observed_xml_tag_names", []),
                "native_balances_or_payments_reported_here": False,
            }
            break
    if status != _EXPECTED_SOURCE_STATUS:
        basic["next_action"] = "Revisar XML CONFÍA del corte en la configuración institucional."
        return basic
    if master != _REQUIRED_MASTER_STATUS:
        basic["status"] = "BLOCKED_MASTER_AT_CUTOFF"
        basic["next_action"] = "Revisar ruta, fecha y unicidad del Maestro original del corte."
        return basic
    if (approval is None) != (bank is None):
        basic["status"] = "BLOCKED_APPROVAL_PAIR_REQUIRED"
        basic["next_action"] = "Proporcionar ambos respaldos independientes o ninguno."
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
    basic["operational_gates"] = build_operational_gates(
        xml_status=status,
        master_status=master,
        approvals_provided=True,
        projection_executed=True,
        contractual_inventory=inventory.get("contractual_source_inventory"),
    )
    basic["next_action"] = (
        "Revisar la cobertura de fuentes y aprobar solo flujos faltantes con "
        "evidencia contractual individual; la proyección sigue siendo PARCIAL."
    )
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
            "Estado de fuentes",
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
    parser.add_argument(
        "--identity-linkage",
        action="store_true",
        help="Auditar claves compuestas en XML reales; sin reconocer flujos ni importes",
    )
    parser.add_argument("--approval")
    parser.add_argument("--bank")
    args = parser.parse_args(argv)
    if args.self_test:
        if args.cutoff or args.approval or args.bank or args.identity_linkage:
            parser.error("--self-test cannot be combined with institutional source arguments")
        if os.environ.get("AIP_EXECUTION_MODE", "").upper() != "CONFIGURED" or os.environ.get(
            "AIP_DEMO_MODE_ENABLED", ""
        ).lower() not in {"false", "0"}:
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
                identity_linkage=args.identity_linkage,
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
