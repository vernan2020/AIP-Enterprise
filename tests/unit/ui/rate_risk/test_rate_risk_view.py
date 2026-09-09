from __future__ import annotations

from PySide6.QtWidgets import QApplication

from aip.ui.modules.rate_risk.views import RateRiskView


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_rate_risk_view_opens_safely_without_configured_source() -> None:
    _app()
    view = RateRiskView()

    assert view.objectName() == "rateRiskWorkspace"
    assert view._tabs.count() == 6
    assert view._tabs.tabText(0) == "Resumen RTILB"
    assert view._tabs.tabText(2) == "GAP SUGEF · 19 bandas"
    assert view._warning_label.isVisibleTo(view) is False or "Sin cálculo RTILB" in (
        view._warning_label.text()
    )
    assert all(label.text() == "N/D" for label in view._kpi_values.values())


def test_rate_risk_view_exposes_expected_audit_tabs() -> None:
    _app()
    view = RateRiskView()

    labels = [view._tabs.tabText(index) for index in range(view._tabs.count())]
    assert labels == [
        "Resumen RTILB",
        "Escenarios VEP",
        "GAP SUGEF · 19 bandas",
        "Curvas",
        "Drill-down",
        "Calidad de Datos",
    ]
