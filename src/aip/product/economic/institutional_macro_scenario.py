from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


ScenarioType = Literal[
    "BASE",
    "ADVERSE",
    "SEVERE",
    "MANAGEMENT",
]

ScenarioStatus = Literal[
    "DRAFT",
    "APPROVED",
    "SUPERSEDED",
]

IndicatorScenarioStatus = Literal[
    "APPROVED",
    "APPROVED_WITH_WARNINGS",
    "REVIEW_REQUIRED",
    "UNAVAILABLE",
]


@dataclass(frozen=True, slots=True)
class InstitutionalMacroScenarioPoint:
    indicator_code: str
    horizon: int
    target_period: date
    point_forecast: float
    lower_bound: float | None
    upper_bound: float | None
    confidence_level: float


@dataclass(frozen=True, slots=True)
class InstitutionalMacroScenarioIndicator:
    indicator_code: str

    statistical_model_name: str | None
    statistical_model_family: str | None

    governance_model_name: str | None
    governance_model_family: str | None

    institutional_status: IndicatorScenarioStatus

    data_as_of_date: date | None
    forecast_origin_period: date | None

    last_observed_value: float | None

    historical_observations: int

    weighted_relative_score: float | None
    improvement_vs_naive: float | None

    dynamic_stability_status: str | None
    dynamic_stability_ratio: float | None

    data_lag_days: int | None
    data_lag_months: int | None
    is_current_period: bool | None

    approved_for_base_scenario: bool

    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]

    points: tuple[
        InstitutionalMacroScenarioPoint,
        ...,
    ]

    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class InstitutionalMacroScenario:
    scenario_id: str
    version: int

    scenario_type: ScenarioType
    status: ScenarioStatus

    dataset_as_of_date: date
    horizon_months: int

    created_at: datetime

    indicators: tuple[
        InstitutionalMacroScenarioIndicator,
        ...,
    ]

    created_by: str
    description: str | None = None

    @property
    def indicator_count(self) -> int:
        return len(
            self.indicators
        )

    @property
    def approved_indicator_count(self) -> int:
        return sum(
            1
            for item in self.indicators
            if item.approved_for_base_scenario
        )

    @property
    def review_required_count(self) -> int:
        return sum(
            1
            for item in self.indicators
            if (
                item.institutional_status
                == "REVIEW_REQUIRED"
            )
        )

    @property
    def unavailable_count(self) -> int:
        return sum(
            1
            for item in self.indicators
            if (
                item.institutional_status
                == "UNAVAILABLE"
            )
        )

    def indicator(
        self,
        indicator_code: str,
    ) -> InstitutionalMacroScenarioIndicator | None:
        code = (
            indicator_code
            .strip()
            .upper()
        )

        for item in self.indicators:
            if (
                item.indicator_code
                .strip()
                .upper()
                == code
            ):
                return item

        return None
