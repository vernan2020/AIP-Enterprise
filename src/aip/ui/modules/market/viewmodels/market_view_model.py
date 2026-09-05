from __future__ import annotations

from dataclasses import asdict, dataclass, field

from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow


@dataclass(frozen=True, slots=True)
class MarketCurveViewData:
    """Contrato de presentación para una curva institucional."""

    curve_id: str
    label: str
    official_model: str
    observation_count: int
    rmse: float
    r_squared: float
    observed_points: tuple[tuple[float, float], ...] = ()
    fitted_points: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True, slots=True)
class RelativeValueViewRow:
    """Fila normalizada de valor relativo para portafolio o mercado."""

    series: str
    issuer: str
    currency: str
    curve_id: str
    tenor: float
    market_yield: float
    curve_yield: float
    spread_bp: float
    classification: str
    market_value_crc: float | None = None
    position_count: int = 0
    market_price: float | None = None
    in_portfolio: bool | None = None


@dataclass(frozen=True, slots=True)
class RotationViewRow:
    """Fila de presentación para la preselección de rotaciones."""

    source_series: str
    target_series: str
    source_issuer: str
    target_issuer: str
    source_spread_bp: float
    target_spread_bp: float
    spread_pickup_bp: float
    screening_status: str
    currency: str = ""
    curve_id: str = ""
    yield_improvement_bp: float = 0.0
    tenor_difference_years: float = 0.0
    rotation_score: float = 0.0
    signal_type: str = ""
    target_in_portfolio: str = ""
    explanation: str = ""

    @property
    def spread_improvement_bp(self) -> float:
        return self.spread_pickup_bp


@dataclass(frozen=True, slots=True)
class MarketViewModel:
    """Modelo inmutable del espacio de Mercado."""

    summary: object
    rows: tuple[MarketRow, ...]
    curve_points: tuple[CurvePoint, ...]
    filters: dict[str, str] = field(default_factory=dict)
    selected_curve: str | None = None
    theme: str = "light"
    status: str = "ready"
    warnings: tuple[str, ...] = ()
    calculation_id: str | None = None
    correlation_id: str | None = None
    loading: bool = False
    error: str | None = None
    curves: tuple[MarketCurveViewData, ...] = ()
    portfolio_relative_value: tuple[RelativeValueViewRow, ...] = ()
    market_relative_value: tuple[RelativeValueViewRow, ...] = ()
    rotation_rows: tuple[RotationViewRow, ...] = ()

    @property
    def market_rows(self) -> tuple[RelativeValueViewRow, ...]:
        """Alias de compatibilidad con la generación visual histórica."""

        return self.market_relative_value

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary.__dict__ if hasattr(self.summary, "__dict__") else {},
            "rows": [asdict(row) for row in self.rows],
            "curve_points": [asdict(curve) for curve in self.curve_points],
            "filters": dict(self.filters),
            "selected_curve": self.selected_curve,
            "theme": self.theme,
            "status": self.status,
            "warnings": list(self.warnings),
            "calculation_id": self.calculation_id,
            "correlation_id": self.correlation_id,
            "loading": self.loading,
            "error": self.error,
            "curves": [asdict(curve) for curve in self.curves],
            "portfolio_relative_value": [asdict(row) for row in self.portfolio_relative_value],
            "market_relative_value": [asdict(row) for row in self.market_relative_value],
            "rotation_rows": [asdict(row) for row in self.rotation_rows],
        }
