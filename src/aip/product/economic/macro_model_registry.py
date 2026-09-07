from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MacroModelFamily = Literal[
    "NAIVE",
    "DRIFT",
    "AR",
    "ARIMA",
    "ETS",
    "ARDL",
    "RIDGE",
    "ELASTIC_NET",
    "GRADIENT_BOOSTING",
]

MacroModelMode = Literal["UNIVARIATE", "MULTIVARIATE_DIRECT"]


@dataclass(frozen=True, slots=True)
class MacroModelSpecification:
    """Governed description of one candidate macro forecasting model."""

    name: str
    family: MacroModelFamily
    mode: MacroModelMode
    complexity_score: int
    enabled: bool = True
    parameters: tuple[tuple[str, str], ...] = ()


class MacroModelRegistry:
    """Single governed source of truth for the macro candidate universe."""

    def __init__(
        self,
        specifications: tuple[MacroModelSpecification, ...] | None = None,
    ) -> None:
        self._specifications = specifications or self.default_specifications()
        names = [item.name for item in self._specifications]
        if len(names) != len(set(names)):
            raise ValueError("Macro model names must be unique")

    def enabled(self) -> tuple[MacroModelSpecification, ...]:
        return tuple(item for item in self._specifications if item.enabled)

    def get(self, model_name: str) -> MacroModelSpecification:
        normalized = model_name.strip().upper()
        for item in self._specifications:
            if item.name.upper() == normalized:
                return item
        raise KeyError(f"Unknown macro model: {model_name}")

    @staticmethod
    def default_specifications() -> tuple[MacroModelSpecification, ...]:
        return (
            MacroModelSpecification("NAIVE", "NAIVE", "UNIVARIATE", 0),
            MacroModelSpecification("DRIFT", "DRIFT", "UNIVARIATE", 1),
            MacroModelSpecification(
                "AR_1",
                "AR",
                "UNIVARIATE",
                2,
                parameters=(("lags", "1"),),
            ),
            MacroModelSpecification(
                "AR_2",
                "AR",
                "UNIVARIATE",
                3,
                parameters=(("lags", "2"),),
            ),
            MacroModelSpecification(
                "ARIMA_1_1_0",
                "ARIMA",
                "UNIVARIATE",
                4,
                parameters=(("order", "1,1,0"),),
            ),
            MacroModelSpecification(
                "ARIMA_0_1_1",
                "ARIMA",
                "UNIVARIATE",
                4,
                parameters=(("order", "0,1,1"),),
            ),
            MacroModelSpecification(
                "ETS_DAMPED",
                "ETS",
                "UNIVARIATE",
                3,
                parameters=(("trend", "add"), ("damped", "true")),
            ),
            MacroModelSpecification(
                "ARDL_DIRECT",
                "ARDL",
                "MULTIVARIATE_DIRECT",
                5,
                parameters=(("target_lags", "1,2,3,6,12"), ("driver_lags", "0,1,3,6,12")),
            ),
            MacroModelSpecification(
                "RIDGE_DIRECT",
                "RIDGE",
                "MULTIVARIATE_DIRECT",
                4,
                parameters=(("alpha", "1.0"),),
            ),
            MacroModelSpecification(
                "ELASTIC_NET_DIRECT",
                "ELASTIC_NET",
                "MULTIVARIATE_DIRECT",
                5,
                parameters=(("alpha", "0.05"), ("l1_ratio", "0.25")),
            ),
            MacroModelSpecification(
                "GRADIENT_BOOSTING_DIRECT",
                "GRADIENT_BOOSTING",
                "MULTIVARIATE_DIRECT",
                7,
                parameters=(("n_estimators", "100"), ("max_depth", "2")),
            ),
        )
