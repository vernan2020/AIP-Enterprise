from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest
from openpyxl import load_workbook
from PySide6.QtCore import QDate

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
    project_sugef210,
)
from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView
from aip.ui.modules.liquidity.views.sugef210_projection_panel import (
    SUGEF210ProjectionPanel,
)


def test_sugef210_panel_shows_compliant_horizons_without_demo_amounts(qt_app):
    panel = SUGEF210ProjectionPanel()
    try:
        panel._date.setDate(QDate(2026, 9, 30))
        assert panel._windows.rowCount() == 17
        assert panel._windows.item(0, 4).text() == "N/D"
        assert panel._windows.item(0, 5).text() == "N/D"
        assert panel._windows.item(8, 1).text() == "08/10/2026"
        assert panel._windows.item(11, 2).text() == "30/10/2026"
        assert panel._windows.item(12, 2).text() == "29/11/2026"
        assert panel._windows.item(13, 2).text() == "29/12/2026"
        assert panel._windows.item(16, 2).text() == "30/09/2027"
        assert panel._accounts.rowCount() == 0
    finally:
        panel.close()


def test_sugef210_xml_inventory_visible_but_not_available_cash(qt_app):
    panel = SUGEF210ProjectionPanel()
    try:
        panel._date.setDate(QDate(2026, 9, 30))
        panel._receive(
            panel._cutoff,
            {
                "status": "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH",
                "xml_records_read": 3,
                "accounts": [
                    {
                        "account_code": "100",
                        "currency_source_code": "1",
                        "record_count": 3,
                        "source_principal": "150000",
                        "classification": "NOT_APPROVED_FOR_CURRENT_ACCOUNT",
                        "master_isin_matches": 1,
                        "unverified_master_overlap": 2,
                    }
                ],
            },
        )
        assert panel._accounts.rowCount() == 1
        assert panel._accounts.item(0, 3).text() == "150000"
        assert "NO CERTIFICADA" in panel._status.text()
        assert all(panel._windows.item(row, 4).text() == "N/D" for row in range(17))
        panel._date.setDate(QDate(2026, 10, 19))
        assert panel._accounts.rowCount() == 0
        assert "No se reutilizan" in panel._status.text()
    finally:
        panel.close()


def test_existing_liquidity_page_includes_sugef210_tab(qt_app):
    view = LiquidityView()
    try:
        names = [view._tabs.tabText(i) for i in range(view._tabs.count())]
        assert "Flujo proyectado · SUGEF 2-10" in names
        assert view._projection_sugef210._windows.rowCount() == 17
    finally:
        view.close()


def test_contractual_xml_source_status_not_a_payment_schedule(qt_app):
    panel = SUGEF210ProjectionPanel()
    try:
        panel._date.setDate(QDate(2026, 9, 30))
        panel._receive(
            panel._cutoff,
            {
                "status": "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH",
                "xml_records_read": 0,
                "accounts": [],
                "record_evidence": [],
                "contractual_source_inventory": [
                    {
                        "source_key": "CREDIT",
                        "file": "NEC2024_Operaciones_5103.Nuevo.xml",
                        "records": 2,
                        "source_currency_balances_not_cashflows": {"1": "100.00"},
                        "dates": [
                            {"field": "FechaVencimiento", "valid": 1, "missing": 1, "invalid": 0}
                        ],
                        "status": "SOURCE_FIELDS_INSPECTED_NOT_A_PAYMENT_SCHEDULE",
                    },
                    {
                        "source_key": "CAPTACIONES",
                        "file": None,
                        "status": "SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO",
                    },
                ],
            },
        )
        assert panel._xml_perimeters.rowCount() == 2
        assert "NO flujos" in panel._XML_PERIMETER_HEADERS[3]
        assert panel._xml_perimeters.item(0, 3).text() == "1: 100.00"
        assert panel._xml_perimeters.item(1, 2).text() == "N/D"
        assert panel._windows.item(0, 4).text() == "N/D"
    finally:
        panel.close()


def test_governed_projection_updates_only_verified_currency_and_resets_on_scenario(qt_app):
    panel = SUGEF210ProjectionPanel()
    try:
        cutoff = date(2026, 9, 30)
        panel._date.setDate(QDate(2026, 9, 30))
        flow = LiquidityProjectionFlow(
            reference="CONTRACT-CREDIT-TEST-001",
            source="TEST-ONLY",
            currency="CRC",
            payment_date=cutoff + timedelta(days=31),
            amount=Decimal("125"),
            side=LiquidityFlowSide.INFLOW,
            area=LiquidityBalanceArea.ASSET,
            evidence=LiquidityEvidence.CONTRACTUAL,
        )
        result = project_sugef210(
            cutoff=cutoff,
            scenario="BASE",
            flows=(flow,),
            opening_liquidity={"CRC": Decimal("10")},
            source_areas_covered=(LiquidityBalanceArea.ASSET,),
            opening_certification_references={"CRC": "ACCOUNT-RECON-TEST"},
        )
        assert not result.certified_comprehensive
        panel.present_governed_projection(result)
        assert panel._windows.item(12, 4).text() == "125"
        assert panel._windows.item(13, 4).text() == "N/D"
        assert panel._windows.item(12, 5).text() == "N/D"
        assert panel._windows.item(12, 9).text() == "135"
        assert panel._windows.item(12, 10).text() == "N/D"
        assert panel._projected_kpis["CRC"].text() == "135"
        assert panel._projected_kpis["USD"].text() == "N/D"
        assert "PARCIAL" in panel._windows.item(12, 6).text()
        panel._scenario.setCurrentText("SYSTEMIC")
        assert panel._governed_projection is None
        assert panel._windows.item(12, 4).text() == "N/D"
        with pytest.raises(ValueError, match="cutoff/scenario"):
            panel.present_governed_projection(result)
    finally:
        panel.close()


def test_governed_partial_projection_can_export_without_xml_inventory(
    qt_app, tmp_path, monkeypatch
):
    panel = SUGEF210ProjectionPanel()
    try:
        cutoff = date(2026, 9, 30)
        panel._date.setDate(QDate(2026, 9, 30))
        result = project_sugef210(
            cutoff=cutoff,
            scenario="BASE",
            flows=(),
            opening_liquidity=None,
        )
        panel.present_governed_projection(result)
        destination = tmp_path / "sugef210_only_partially_supported.xlsx"
        monkeypatch.setattr(
            "aip.ui.modules.liquidity.views.sugef210_projection_panel."
            "QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (str(destination), "Excel (*.xlsx)"),
        )
        panel.export_reconciliation()
        assert destination.is_file()
        workbook = load_workbook(destination, read_only=True, data_only=True)
        try:
            assert "Flujo proyectado 365d" in workbook.sheetnames
            projection = workbook["Flujo proyectado 365d"]
            assert projection.max_row == 35
            assert projection.cell(2, 6).value == "CRC"
            assert projection.cell(2, 15).value == "N/D"
            assert projection.cell(2, 7).value == "N/D"
            metadata = dict(workbook["Control"].iter_rows(values_only=True))
            assert metadata["flujo_integral_certificado"] == "NO"
            assert metadata["escenario"] == "BASE"
        finally:
            workbook.close()
    finally:
        panel.close()


def test_governed_projection_rejects_incomplete_horizon_and_currency_rows(qt_app):
    panel = SUGEF210ProjectionPanel()
    try:
        cutoff = date(2026, 9, 30)
        panel._date.setDate(QDate(2026, 9, 30))
        correct = project_sugef210(
            cutoff=cutoff, scenario="BASE", flows=(), opening_liquidity=None
        )
        with pytest.raises(ValueError, match="fixed SUGEF210"):
            panel.present_governed_projection(
                replace(correct, windows=correct.windows[:-1])
            )
        with pytest.raises(ValueError, match="do not reconcile"):
            panel.present_governed_projection(
                replace(correct, rows=correct.rows[:-1])
            )
        assert panel._windows.item(12, 4).text() == "N/D"
    finally:
        panel.close()
