from __future__ import annotations

import unittest
from pathlib import Path

from aip.product.configured.liquidity.financial_plan_path import (
    configured_financial_plan_path,
)


class FinancialPlanPathTests(unittest.TestCase):
    def test_missing_configuration_never_guesses_a_source(self) -> None:
        self.assertIsNone(configured_financial_plan_path({}))

    def test_explicit_plan_path_takes_precedence_over_legacy_alias(self) -> None:
        environment = {
            "AIP_FINANCIAL_PLAN_2026_PATH": "/institutional/plan-2026.xlsx",
            "AIP_FINANCIAL_PLAN_PATH": "/legacy/plan.xlsx",
        }
        self.assertEqual(
            configured_financial_plan_path(environment),
            Path("/institutional/plan-2026.xlsx"),
        )

    def test_legacy_source_path_remains_supported(self) -> None:
        self.assertEqual(
            configured_financial_plan_path(
                {"AIP_FINANCIAL_PLAN_PATH": '"/institutional/plan.xlsx"'}
            ),
            Path("/institutional/plan.xlsx"),
        )


if __name__ == "__main__":
    unittest.main()
