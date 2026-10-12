from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication

from aip.domain.portfolio.services.portfolio_optimization_preflight_service import (
    HistoryReadiness,
    OptimizationPreflightResult,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import (
    ScenarioRiskComparison,
    ScenarioRiskSnapshot,
)
from aip.ui.modules.portfolio.views.portfolio_markowitz_view import PortfolioMarkowitzView


@pytest.fixture
def panel(qt_app: QApplication) -> PortfolioMarkowitzView:
    view = PortfolioMarkowitzView()
    yield view
    view.close()
    view.deleteLater()
    qt_app.processEvents()


def test_markowitz_view_never_claims_optimized_portfolio_without_history(
    panel: PortfolioMarkowitzView,
) -> None:
    panel.bind_portfolio_cutoff("2026-10-02")
    assert panel._status.text() == "MISSING_RETURNS"
    assert "NO DISPONIBLES" in panel._warning.text()
    assert panel.preflight is None


def test_markowitz_preflight_is_cutoff_scoped(panel: PortfolioMarkowitzView) -> None:
    panel.bind_portfolio_cutoff("2026-10-02")
    readiness = OptimizationPreflightResult(
        status=HistoryReadiness.READY,
        reason="Audited aligned total returns",
        asset_names=("A", "B"),
        observation_dates=(date(2026, 9, 30), date(2026, 10, 1)),
        aligned_returns=((0.01, 0.02), (0.02, 0.01)),
        periods_per_year=252,
    )
    with pytest.raises(ValueError, match="cutoff"):
        panel.bind_preflight(readiness, cutoff="2026-10-03")
    panel.bind_preflight(readiness, cutoff="2026-10-02")
    assert panel._asset_count.text() == "2"
    assert panel._observations.text() == "2"
    assert panel._status.text() == "READY"
    assert "Falta aprobar" in panel._warning.text()
    panel.bind_portfolio_cutoff("2026-10-03")
    assert panel.preflight is None
    assert panel._status.text() == "MISSING_RETURNS"


def test_markowitz_invalid_preflight_remains_disabled(panel: PortfolioMarkowitzView) -> None:
    panel.bind_portfolio_cutoff("2026-10-02")
    panel.bind_preflight(
        OptimizationPreflightResult(
            status=HistoryReadiness.INCOMPATIBLE_CURRENCY,
            reason="Unconverted USD total returns",
        ),
        cutoff="2026-10-02",
    )
    assert "No se permite optimizar" in panel._warning.text()


def test_scenario_risk_display_invalidates_on_new_cutoff(
    panel: PortfolioMarkowitzView,
) -> None:
    panel.bind_portfolio_cutoff("2026-10-02")
    actual = ScenarioRiskSnapshot(
        modified_duration_years=Decimal("1.8"),
        dv01_crc=Decimal("180"),
        hqla_fraction=Decimal("0.96"),
        credit_rwa_crc=Decimal("150000"),
        breached_limits=(),
        status="PASS",
    )
    proposal = ScenarioRiskSnapshot(
        modified_duration_years=Decimal("4.2"),
        dv01_crc=Decimal("420"),
        hqla_fraction=Decimal("0.84"),
        credit_rwa_crc=Decimal("600000"),
        breached_limits=("modified_duration", "hqla"),
        status="BREACH",
    )
    review = ScenarioRiskComparison(
        cutoff=date(2026, 10, 2),
        portfolio_value_crc=Decimal("1000000"),
        current=actual,
        proposed=proposal,
        missing_limits=("credit_rwa",),
        policy_version="APPROVED-2026",
    )
    with pytest.raises(ValueError, match="cutoff"):
        panel.bind_risk_comparison(review, cutoff="2026-10-03")
    panel.bind_risk_comparison(review, cutoff="2026-10-02")
    assert panel.scenario_risk is review
    assert "Propuesta: BREACH" in panel._scenario_risk_status.text()
    assert "modified_duration, hqla" in panel._scenario_risk_detail.text()
    assert "credit_rwa" in panel._scenario_risk_detail.text()
    panel.bind_portfolio_cutoff("2026-10-03")
    assert panel.scenario_risk is None
    assert "SIN DATOS" in panel._scenario_risk_status.text()
