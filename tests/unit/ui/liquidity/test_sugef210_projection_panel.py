from __future__ import annotations

from PySide6.QtCore import QDate

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
