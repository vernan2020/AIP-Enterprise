from __future__ import annotations

from aip.product.demo.data.demo_dataset import DemoDataset
from aip.product.demo.data.demo_liquidity_data import DemoLiquidityData
from aip.product.demo.data.demo_market_data import DemoMarketData
from aip.product.demo.data.demo_portfolio_data import DemoPortfolioData


def test_demo_dataset_is_deterministic_and_populated() -> None:
    dataset = DemoDataset(
        valuation_date=DemoPortfolioData.build()["valuation_date"],
        portfolio=DemoPortfolioData.build(),
        market=DemoMarketData.build(),
        liquidity=DemoLiquidityData.build(),
        treasury={"decision": "BUY"},
        executive={"status": "READY"},
        status={"mode": "DEMO"},
    )
    assert dataset.portfolio["portfolio_name"] == "Coopealianza Demo Portfolio"
    assert dataset.market["market_status"] == "Ready"
    assert dataset.liquidity["liquidity_gap"] == 0.0
    assert dataset.treasury["decision"] == "BUY"
    assert dataset.status["mode"] == "DEMO"
