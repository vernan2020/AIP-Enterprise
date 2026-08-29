from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IntegrationOrder = Literal[
    "I(0)",
    "I(1)",
    "UNDETERMINED",
]


@dataclass(
    frozen=True,
    slots=True,
)
class ADFTestResult:
    indicator_code: str
    transformation: str

    statistic: float | None
    p_value: float | None

    observations: int
    lags_used: int | None

    critical_value_1pct: float | None
    critical_value_5pct: float | None
    critical_value_10pct: float | None

    stationary: bool
    diagnostic: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class StationarityDiagnostic:
    indicator_code: str

    level_test: ADFTestResult
    difference_test: ADFTestResult

    integration_order: IntegrationOrder


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricDiagnosticsResult:
    observations: int

    diagnostics: tuple[
        StationarityDiagnostic,
        ...,
    ]

    @property
    def stationary_in_levels(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            item.indicator_code for item in self.diagnostics if item.integration_order == "I(0)"
        )

    @property
    def integrated_order_one(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            item.indicator_code for item in self.diagnostics if item.integration_order == "I(1)"
        )

    @property
    def undetermined(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            item.indicator_code
            for item in self.diagnostics
            if item.integration_order == "UNDETERMINED"
        )
