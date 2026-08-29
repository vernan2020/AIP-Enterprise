from __future__ import annotations

from typing import Any

from src.extensions.coopealianza.liquidity.mil.models.mil_result import MilResult


class MilReportBuilder:
    """Build deterministic, explainable MIL reports."""

    def build(self, result: MilResult) -> dict[str, Any]:
        positions = [
            {
                "position_id": position.position_id,
                "instrument_id": position.instrument_id,
                "issuer": position.issuer,
                "classification": position.classification,
                "eligibility_status": position.eligibility_status.value,
                "haircut": str(position.haircut),
                "adjusted_value": str(position.adjusted_value),
                "market_value": str(position.market_value),
                "blocking_factors": list(position.blocking_factors),
                "warning_factors": list(position.warning_factors),
            }
            for position in result.positions
        ]
        capacity = {
            "total_market_value_evaluated": str(result.capacity.total_market_value_evaluated),
            "eligible_adjusted_collateral_value": format(
                result.capacity.eligible_adjusted_collateral_value, "f"
            )
            .rstrip("0")
            .rstrip(".")
            or "0",
            "conditional_adjusted_collateral_value": format(
                result.capacity.conditional_adjusted_collateral_value, "f"
            )
            .rstrip("0")
            .rstrip(".")
            or "0",
            "total_potential_collateral_capacity": format(
                result.capacity.total_potential_collateral_capacity, "f"
            )
            .rstrip("0")
            .rstrip(".")
            or "0",
            "capacity_by_issuer": {
                key: format(value, "f").rstrip("0").rstrip(".") or "0"
                for key, value in sorted(result.capacity.capacity_by_issuer.items())
            },
            "capacity_by_currency": {
                key: format(value, "f").rstrip("0").rstrip(".") or "0"
                for key, value in sorted(result.capacity.capacity_by_currency.items())
            },
            "capacity_by_maturity_band": {
                key: format(value, "f").rstrip("0").rstrip(".") or "0"
                for key, value in sorted(result.capacity.capacity_by_maturity_band.items())
            },
            "capacity_by_classification": {
                key: format(value, "f").rstrip("0").rstrip(".") or "0"
                for key, value in sorted(result.capacity.capacity_by_classification.items())
            },
        }
        explanation = {
            "conclusion": (
                result.explanation.concise_conclusion
                if result.explanation is not None
                else "MIL evaluation completed"
            ),
            "supporting_factors": (
                [
                    {
                        "name": factor.name,
                        "value": str(factor.value),
                        "contribution": str(factor.contribution),
                    }
                    for factor in result.explanation.supporting_factors
                ]
                if result.explanation is not None
                else []
            ),
        }
        return {
            "portfolio_reference": result.portfolio_reference,
            "configuration_version": result.configuration_version,
            "positions": positions,
            "capacity": capacity,
            "status_counts": dict(sorted(result.status_counts.items())),
            "explanation": explanation,
        }
