from __future__ import annotations

from datetime import date

from aip.ui.modules.rate_risk.views.investment_master_evidence_panel import (
    InvestmentMasterEvidencePanel,
)
from aip.ui.modules.rate_risk.views.rate_risk_workspace import RateRiskWorkspace


def _report() -> dict[str, object]:
    return {
        "status": "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED",
        "accepted_positions": 3,
        "rejected_rows": 0,
        "warning_count": 0,
        "certification_status": "BLOCKED",
        "blocking_requirements": ["INV-PRINCIPAL"],
        "not_assessed_requirements": ["INV-CASHFLOWS"],
        "maturity_bands": [
            {
                "source_currency": "CRC",
                "ordinal": 4,
                "band": "3 a 6 meses",
                "positions": 2,
                "source_principal": "1234567.89",
            }
        ],
        "maturity_exclusions": [
            {
                "source_currency": "(SIN MONEDA NATIVA)",
                "reason": "MISSING_NATIVE_CURRENCY",
                "positions": 1,
                "valid_source_principal": "0",
            }
        ],
        "currencies": [
            {
                "source_currency": "CRC",
                "positions": 2,
                "source_principal": "1234567.89",
                "principal_records": 2,
                "principal_missing": 0,
                "maturity_present": 2,
                "maturity_missing_or_past": 0,
            },
            {
                "source_currency": "(SIN MONEDA NATIVA)",
                "positions": 1,
                "source_principal": "0",
                "principal_records": 0,
                "principal_missing": 1,
                "maturity_present": 1,
                "maturity_missing_or_past": 0,
            },
        ],
    }


def test_investment_panel_shows_real_source_currency_and_certification(qt_app):
    panel = InvestmentMasterEvidencePanel()
    try:
        cutoff = date(2026, 9, 30)
        panel.set_cutoff(cutoff)
        panel._receive_result(cutoff, _report())
        assert panel._table.rowCount() == 2
        assert panel._table.item(0, 2).text() == "1.234.567,89"
        assert panel._table.item(1, 0).text() == "(SIN MONEDA NATIVA)"
        assert panel._table.item(1, 4).text() == "1"
        assert panel._bands.rowCount() == 1
        assert panel._bands.item(0, 1).text() == "4. 3 a 6 meses"
        assert panel._bands.item(0, 3).text() == "1.234.567,89"
        assert panel._excluded.rowCount() == 1
        assert "Falta moneda" in panel._excluded.item(0, 1).text()
        assert "BLOCKED" in panel._certification.text()
        assert "Sin GAP" in panel._certification.text()
    finally:
        panel.close()


def test_investment_panel_does_not_reuse_previous_cutoff(qt_app):
    panel = InvestmentMasterEvidencePanel()
    try:
        panel.set_cutoff(date(2026, 9, 30))
        panel._receive_result(date(2026, 9, 30), _report())
        panel.set_cutoff(date(2026, 10, 15))
        panel._receive_result(date(2026, 9, 30), _report())
        assert panel._table.rowCount() == 0
        assert panel._bands.rowCount() == 0
        assert panel._excluded.rowCount() == 0
        assert "15/10/2026" in panel._status.text()
    finally:
        panel.close()


def test_workspace_integrates_investment_master_tab(qt_app):
    workspace = RateRiskWorkspace(
        valuation_date_provider=lambda: date(2026, 9, 30), controller=None
    )
    try:
        text = [workspace.view._tabs.tabText(i) for i in range(workspace.view._tabs.count())]
        assert "Inversiones · Maestro" in text
        assert "Bandeo 19 · evidencia" in text
    finally:
        workspace.close()
