from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class MacroProjectionRow:
    """One monthly row from the governed institutional macro scenario."""

    period: date
    fx_sell: float
    tpm: float
    tbp: float
    tri_crc_12m: float
    tri_usd_12m: float
    inflation: float
    imae: float

    def value_for(self, code: str) -> float:
        mapping = {
            "FX_SELL": self.fx_sell,
            "TPM": self.tpm,
            "TBP": self.tbp,
            "TRI_CRC_12M": self.tri_crc_12m,
            "TRI_USD_12M": self.tri_usd_12m,
            "INFLATION": self.inflation,
            "IMAE": self.imae,
        }
        return mapping[code]


@dataclass(frozen=True, slots=True)
class MacroProjectionViewModel:
    """Immutable presentation contract for the approved macro scenario."""

    status: str = "UNAVAILABLE"
    scenario_id: str = "-"
    version: int = 0
    scenario_type: str = "-"
    scenario_status: str = "-"
    dataset_as_of_date: date | None = None
    horizon: int = 0
    rows: tuple[MacroProjectionRow, ...] = field(default_factory=tuple)
    diagnostic: str | None = None

    @property
    def first_period(self) -> date | None:
        return self.rows[0].period if self.rows else None

    @property
    def last_period(self) -> date | None:
        return self.rows[-1].period if self.rows else None


@dataclass(frozen=True, slots=True)
class MacroModelMetricView:
    horizon: str
    rmse: str
    mae: str
    bias: str
    directional_accuracy: str
    relative_rmse: str


@dataclass(frozen=True, slots=True)
class MacroModelComparisonView:
    rank: str
    model_name: str
    family: str
    status: str
    weighted_score: str
    improvement_vs_naive: str
    metrics: tuple[MacroModelMetricView, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MacroEnsembleWeightView:
    model_name: str
    family: str
    weight: str


@dataclass(frozen=True, slots=True)
class MacroForecastPointView:
    horizon: int
    period: date
    forecast: float
    lower_80: float | None
    upper_80: float | None
    lower_95: float | None
    upper_95: float | None


@dataclass(frozen=True, slots=True)
class MacroForecastLabViewModel:
    indicator_code: str = "TPM"
    indicator_label: str = "TPM"
    status: str = "UNAVAILABLE"
    forecast_origin: date | None = None
    historical_observations: int = 0
    champion_model: str = "-"
    champion_family: str = "-"
    confidence_score: str = "-"
    projection_1m: str = "-"
    projection_3m: str = "-"
    projection_6m: str = "-"
    projection_12m: str = "-"
    models: tuple[MacroModelComparisonView, ...] = field(default_factory=tuple)
    ensemble: tuple[MacroEnsembleWeightView, ...] = field(default_factory=tuple)
    points: tuple[MacroForecastPointView, ...] = field(default_factory=tuple)
    diagnostic: str | None = None
