from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_analysis.liquidity import (
    LiquidityCoverageCalculator,
    LiquidityCoverageInput,
)


def test_liquidity_formula_uses_four_exact_components() -> None:
    result = LiquidityCoverageCalculator().calculate(
        LiquidityCoverageInput(
            cash_and_due_from=Decimal("100"),
            investments=Decimal("200"),
            available_investments=Decimal("50"),
            public_obligations=Decimal("700"),
        )
    )

    assert result.complete is True
    assert result.value == Decimal("0.5")


def test_liquidity_keeps_missing_component_unavailable() -> None:
    result = LiquidityCoverageCalculator().calculate(
        LiquidityCoverageInput(
            cash_and_due_from=Decimal("100"),
            investments=None,
            available_investments=Decimal("50"),
            public_obligations=Decimal("700"),
        )
    )

    assert result.complete is False
    assert result.value is None
    assert result.missing_components == ("12000000",)
