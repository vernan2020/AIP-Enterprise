from __future__ import annotations

from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.rate_risk.views.rate_risk_view import RateRiskView


def test_executive_cockpit_uses_primary_kpis_and_secondary_context(qt_app) -> None:
    workspace = ExecutiveWorkspace()

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
        "Sin cálculo disponible" in label.text()
        for label in view._empty_state_labels.values()
    )
