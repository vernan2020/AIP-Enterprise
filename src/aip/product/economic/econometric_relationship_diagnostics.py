from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class CorrelationDiagnostic:
    left_indicator: str
    right_indicator: str
    coefficient: float


@dataclass(
    frozen=True,
    slots=True,
)
class LaggedRelationshipDiagnostic:
    driver: str
    target: str
    lag: int
    coefficient: float
    observations: int


@dataclass(
    frozen=True,
    slots=True,
)
class VIFDiagnostic:
    indicator_code: str
    vif: float | None
    status: str
    diagnostic: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class LagSelectionDiagnostic:
    observations: int
    variables: int
    maxlags_evaluated: int

    aic: int | None
    bic: int | None
    hqic: int | None
    fpe: int | None

    diagnostic: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class JohansenDiagnostic:
    variables: tuple[
        str,
        ...,
    ]

    observations: int
    deterministic_order: int
    lag_differences: int

    rank_5pct: int | None

    trace_statistics: tuple[
        float,
        ...,
    ]

    critical_values_5pct: tuple[
        float,
        ...,
    ]

    diagnostic: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricRelationshipDiagnosticsResult:
    observations: int

    correlations: tuple[
        CorrelationDiagnostic,
        ...,
    ]

    lagged_relationships: tuple[
        LaggedRelationshipDiagnostic,
        ...,
    ]

    vif: tuple[
        VIFDiagnostic,
        ...,
    ]

    lag_selection: LagSelectionDiagnostic
    johansen: JohansenDiagnostic

    def strongest_lagged_relationships(
        self,
        *,
        limit: int = 10,
    ) -> tuple[
        LaggedRelationshipDiagnostic,
        ...,
    ]:
        if limit <= 0:
            return ()

        ordered = sorted(
            self.lagged_relationships,
            key=lambda item: abs(item.coefficient),
            reverse=True,
        )

        return tuple(ordered[:limit])
