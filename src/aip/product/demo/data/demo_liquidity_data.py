from __future__ import annotations

from typing import Any


class DemoLiquidityData:
    """Deterministic liquidity data for demo mode."""

    @staticmethod
    def build() -> dict[str, Any]:
        return {
            "liquidity_date": "2026-07-29",
            "cash_position": 100.00,
            "net_cash_flow": 10.00,
            "liquidity_gap": 0.00,
            "hqla_capacity": 80.00,
            "mil_eligible_capacity": 60.00,
            "stress_result": "Stable",
            "policy_status": "Compliant",
            "cashflows": [
                {
                    "section": "cashflow",
                    "label": "Inflows",
                    "value": "100.00",
                    "bucket": "T+0",
                    "status": "Healthy",
                },
            ],
            "gaps": [
                {
                    "section": "gap",
                    "label": "Gap",
                    "value": "0.00",
                    "bucket": "T+1",
                    "status": "Balanced",
                },
            ],
            "hqla_rows": [
                {
                    "section": "hqla",
                    "label": "Eligible",
                    "value": "80.00",
                    "policy_reference": "POL-1",
                    "status": "Eligible",
                },
            ],
            "mil_rows": [
                {
                    "section": "mil",
                    "label": "Eligible Assets",
                    "value": "60.00",
                    "policy_reference": "POL-2",
                    "status": "Eligible",
                },
            ],
            "stress_rows": [
                {"section": "stress", "label": "Scenario", "value": "Baseline", "status": "Stable"},
            ],
        }
