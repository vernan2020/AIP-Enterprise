from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GovernanceStatus = Literal[
    "APPROVED",
    "APPROVED_WITH_WARNINGS",
    "REVIEW_REQUIRED",
    "UNAVAILABLE",
]


@dataclass(frozen=True, slots=True)
class HorizonBacktestMetrics:
    """
    Métricas out-of-sample para un horizonte específico.
    """

    horizon_months: int
    observations: int
    rmse: float | None
    mae: float | None
    bias: float | None
    naive_rmse: float | None
    relative_rmse: float | None


@dataclass(frozen=True, slots=True)
class ModelHorizonGovernance:
    """
    Resultado multi-horizonte de un modelo candidato.
    """

    model_name: str
    model_family: str
    parameters: tuple[tuple[str, str], ...]
    horizons: tuple[HorizonBacktestMetrics, ...]
    weighted_relative_score: float | None
    improvement_vs_naive: float | None
    available_horizons: int
    warning_count: int
    failed_estimations: int

    @property
    def available(self) -> bool:
        return self.weighted_relative_score is not None and self.available_horizons > 0

    def metrics_for_horizon(
        self,
        horizon_months: int,
    ) -> HorizonBacktestMetrics | None:
        for item in self.horizons:
            if item.horizon_months == horizon_months:
                return item

        return None


@dataclass(frozen=True, slots=True)
class DynamicStabilityDiagnostic:
    """
    Contrasta el desplazamiento proyectado a 12 meses
    con movimientos históricos reales a 12 meses.

    No impone límites económicos exógenos.
    """

    historical_observations: int
    historical_change_observations: int
    last_observed_value: float | None
    projected_12m_value: float | None
    projected_change_12m: float | None
    historical_abs_change_p95: float | None
    stability_ratio: float | None
    status: str
    diagnostic: str | None


@dataclass(frozen=True, slots=True)
class ForecastGovernanceResult:
    """
    Resultado final de gobernanza de modelo.

    statistical_model_name:
        ganador del selector one-step existente.

    governance_model_name:
        modelo recomendado luego de evaluar desempeño
        multi-horizonte y estabilidad dinámica.
    """

    indicator_code: str
    status: GovernanceStatus
    statistical_model_name: str | None
    statistical_model_family: str | None
    governance_model_name: str | None
    governance_model_family: str | None
    weighted_relative_score: float | None
    improvement_vs_naive: float | None
    materiality_threshold: float
    horizon_results: tuple[ModelHorizonGovernance, ...]
    dynamic_stability: DynamicStabilityDiagnostic | None
    warnings: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()
    diagnostic: str | None = None

    @property
    def approved(self) -> bool:
        return self.status in (
            "APPROVED",
            "APPROVED_WITH_WARNINGS",
        )

    @property
    def statistical_and_governance_agree(
        self,
    ) -> bool:
        return (
            self.statistical_model_name is not None
            and self.statistical_model_name == self.governance_model_name
        )

    def model_result(
        self,
        model_name: str,
    ) -> ModelHorizonGovernance | None:
        for item in self.horizon_results:
            if item.model_name == model_name:
                return item

        return None
