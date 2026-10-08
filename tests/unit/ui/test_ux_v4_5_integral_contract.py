from __future__ import annotations

from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel
from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.rate_risk.views.rate_risk_view import RateRiskView


class _StaticExecutivePresenter:
    def __init__(self) -> None:
        self._model = ExecutiveViewModel(
            title="PANEL EJECUTIVO",
            subtitle="Portafolio · Liquidez · Mercado · Macroeconomía",
            status="loaded",
            valuation_date="2026-09-30",
            portfolio_market_value="₡1.00 MM",
            weighted_yield="1.00%",
            modified_duration="1.00",
            hqla_percent="1.0%",
            mil_percent="1.0%",
            liquidity_gap="₡0.00 MM",
            icl_total="1.00",
            data_quality_status="LISTO",
        )

    def build_view_model(self) -> ExecutiveViewModel:
        return self._model

    def refresh(self) -> ExecutiveViewModel:
        return self._model


def test_executive_cockpit_uses_primary_kpis_and_secondary_context(qt_app) -> None:
    workspace = ExecutiveWorkspace(presenter=_StaticExecutivePresenter())

    assert tuple(workspace._kpis) == (
        "portfolio",
        "yield",
        "duration",
        "hqla",
        "gap",
        "icl",
    )
    assert tuple(workspace._context_labels) == (
        "mil",
        "rv",
        "quality",
        "macro",
        "horizon",
    )
    assert "UX V" not in workspace._subtitle.text()

    workspace.deleteLater()
    qt_app.processEvents()


def test_rate_risk_is_data_ready_without_simulated_results(qt_app) -> None:
    view = RateRiskView()

    assert all(label.text() == "N/D" for label in view._kpi_values.values())
    assert set(view._empty_state_labels) == {
        "scenarios",
        "gap",
        "curves",
        "flows",
        "quality",
    }
    assert all(
        "Sin cálculo disponible" in label.text() for label in view._empty_state_labels.values()
    )

    view.deleteLater()
    qt_app.processEvents()
