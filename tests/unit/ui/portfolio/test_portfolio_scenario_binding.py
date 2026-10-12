from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    ExposureClass,
)
from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_scenario_evidence_bridge import (
    VerifiedPositionMarketRisk,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskPolicy
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView


def _positions(cutoff: date) -> tuple[VerifiedCapitalPosition, ...]:
    def position(key: str, cls: ExposureClass, regulatory: str) -> VerifiedCapitalPosition:
        return VerifiedCapitalPosition(
            position_key=key,
            isin=f"TEST-ISIN-{key}",
            issuer=f"Fixture {key}",
            currency="CRC",
            cutoff=cutoff,
            invested_amount_crc=Decimal("500"),
            regulatory_exposure_crc=Decimal(regulatory),
            annual_net_yield=Decimal("0.04"),
            exposure_class=cls,
            classification_effective_date=cutoff,
            invested_amount_source="verified acquisition fixture",
            regulatory_exposure_source="verified exposure fixture",
            net_yield_source="verified yield fixture",
            classification_source="verified classification fixture",
        )

    return (
        position("A", ExposureClass.GOVERNMENT_CRC, "600"),
        position("B", ExposureClass.UNRATED, "400"),
    )


def _risks(cutoff: date) -> tuple[VerifiedPositionMarketRisk, ...]:
    def risk(key: str, value: str, duration: str) -> VerifiedPositionMarketRisk:
        return VerifiedPositionMarketRisk(
            position_key=key,
            cutoff=cutoff,
            market_value_crc=Decimal(value),
            modified_duration_years=Decimal(duration),
            dv01_crc=Decimal("0.01"),
            eligible_hqla_value_crc=Decimal(value) * Decimal("0.90"),
            market_value_source="approved vector fixture",
            duration_source="approved duration fixture",
            dv01_source="approved DV01 fixture",
            hqla_source="approved liquidity classification fixture",
        )

    return (risk("A", "600", "1"), risk("B", "400", "5"))


@pytest.fixture
def portfolio_view(qt_app):
    view = PortfolioView()
    yield view
    view.close()
    view.deleteLater()
    qt_app.processEvents()


def test_scenario_bridge_updates_portfolio_ui_only_with_matching_cutoff(
    portfolio_view: PortfolioView,
) -> None:
    cutoff = str(portfolio_view.view_model().summary.valuation_date)
    observed_date = date.fromisoformat(cutoff)
    policy = ScenarioRiskPolicy(
        cutoff=observed_date,
        effective_date=observed_date,
        policy_version="TEST-APPROVED-POLICY",
        approval_reference="signed policy fixture",
        max_modified_duration_years=Decimal("3"),
        min_hqla_fraction=Decimal("0.5"),
    )
    review = portfolio_view.evaluate_and_bind_verified_scenario(
        _positions(observed_date),
        _risks(observed_date),
        {"A": Decimal("0.2"), "B": Decimal("0.8")},
        cutoff=cutoff,
        portfolio_market_value_crc=Decimal("1000"),
        portfolio_valuation_source="audited sum fixture",
        policy=policy,
    )
    assert review.position_keys == ("A", "B")
    assert review.comparison.current.status == "INCOMPLETE"
    assert review.comparison.proposed.status == "BREACH"
    assert portfolio_view._markowitz.scenario_risk is review.comparison
    assert "Propuesta: BREACH" in portfolio_view._markowitz._scenario_risk_status.text()
    with pytest.raises(ValueError, match="cutoff"):
        portfolio_view.evaluate_and_bind_verified_scenario(
            _positions(observed_date),
            _risks(observed_date),
            {"A": Decimal("0.2"), "B": Decimal("0.8")},
            cutoff="2035-01-01",
            portfolio_market_value_crc=Decimal("1000"),
            portfolio_valuation_source="audited sum fixture",
            policy=policy,
        )
    assert portfolio_view._markowitz.scenario_risk is review.comparison
