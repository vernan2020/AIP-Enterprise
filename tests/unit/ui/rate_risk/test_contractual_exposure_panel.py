from __future__ import annotations

from datetime import date

from aip.ui.modules.rate_risk.views.contractual_exposure_panel import (
    ContractualExposurePanel,
)
from aip.ui.modules.rate_risk.views.rate_risk_workspace import RateRiskWorkspace


def _source_result() -> list[dict[str, object]]:
    return [
        {
            "source": "CREDIT",
            "records": 2,
            "groups": [
                {
                    "currency_code": "CRC",
                    "category_codes": {"TipoOperacion": "3"},
                    "records": 1,
                    "principal_balance": "100.50",
                    "missing_by_field": {
                        "FechaProximoPagoPrincipal": {
                            "records": 1,
                            "principal_balance": "100.50",
                        },
                        "FechaProximoPagoIntereses": {
                            "records": 1,
                            "principal_balance": "100.50",
                        },
                    },
                },
                {
                    "currency_code": "USD",
                    "category_codes": {"TipoOperacion": "3"},
                    "records": 1,
                    "principal_balance": "20.25",
                    "missing_by_field": {},
                },
            ],
        },
    ]


def test_panel_displays_real_source_shape_without_currency_conversion(qt_app) -> None:
    panel = ContractualExposurePanel()
    try:
        panel.set_cutoff(date(2026, 9, 30))
        assert panel._table.rowCount() == 0
        assert panel._run_button.isEnabled()
        panel._receive_result(date(2026, 9, 30), _source_result())
        assert panel._table.rowCount() == 2
        assert panel._table.item(0, 1).text() == "CRC"
        assert panel._table.item(0, 4).text() == "100,50"
        assert panel._table.item(0, 5).text() == "1"
        assert panel._table.item(1, 1).text() == "USD"
        assert panel._table.item(1, 4).text() == "20,25"
        assert panel._table.item(1, 5).text() == "N/A"
        assert "2 registros" in panel._status.text()
        assert "sin cálculo VEP/ΔNII" in panel._status.text()
    finally:
        panel.close()


def test_panel_rejects_stale_results_on_cutoff_change(qt_app) -> None:
    panel = ContractualExposurePanel()
    try:
        panel.set_cutoff(date(2026, 9, 30))
        panel._receive_result(date(2026, 9, 30), _source_result())
        panel.set_cutoff(date(2026, 10, 15))
        panel._receive_result(date(2026, 9, 30), _source_result())
        assert panel._table.rowCount() == 0
        assert "15/10/2026" in panel._status.text()
        panel._receive_error(date(2026, 10, 15), "Diagnóstico bloqueado.")
        assert panel._table.rowCount() == 0
    finally:
        panel.close()


def test_workspace_exposes_contractual_evidence_as_independent_tab(qt_app) -> None:
    workspace = RateRiskWorkspace(
        valuation_date_provider=lambda: date(2026, 10, 15),
        controller=None,
    )
    try:
        assert workspace._contractual_exposure_panel._table.rowCount() == 0
        labels = [workspace.view._tabs.tabText(i) for i in range(workspace.view._tabs.count())]
        assert "XML contractual · auditoría" in labels
        assert all(v.text() == "N/D" for v in workspace.view._kpi_values.values())
        assert "15/10/2026" in workspace._contractual_exposure_panel._status.text()
    finally:
        workspace.close()


def test_audit_table_preserves_exact_amounts_and_describes_xml_codes(qt_app) -> None:
    panel = ContractualExposurePanel()
    try:
        panel.set_cutoff(date(2026, 9, 30))
        assert panel._grouped_number("1234567890123456.987654") == (
            "1.234.567.890.123.456,987654"
        )
        panel._receive_result(date(2026, 9, 30), _source_result())
        assert panel._table.columnWidth(2) >= 300
        assert panel._table.horizontalHeader().stretchLastSection() is False
        assert "Operación=3" in panel._table.item(0, 2).text()
        assert "TipoOperacion=3" in panel._table.item(0, 2).toolTip()
        assert "100.50" in panel._table.item(0, 4).toolTip()
        assert "NO intereses devengados" in panel._table.horizontalHeaderItem(8).toolTip()
        panel._filter_input.setText("USD")
        assert panel._table.isRowHidden(0)
        assert not panel._table.isRowHidden(1)
        panel._filter_input.clear()
        assert not panel._table.isRowHidden(0)
        assert not panel._table.isRowHidden(1)
    finally:
        panel.close()
