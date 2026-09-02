from __future__ import annotations

from dataclasses import asdict, dataclass, field

from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow


@dataclass(frozen=True, slots=True)
class MarketCurveViewData:
    """Presentation contract for one institutional yield curve."""

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
    """Normalized relative-value row for portfolio or market screens."""

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
    market_price: float | None = None
    in_portfolio: bool | None = None


@dataclass(frozen=True, slots=True)
class RotationViewRow:
    """Normalized presentation row for preliminary rotation screening."""

    source_series: str
    target_series: str
    source_issuer: str
    target_issuer: str
    source_spread_bp: float
    target_spread_bp: float
    spread_pickup_bp: float
    screening_status: str


@dataclass(frozen=True, slots=True)
class MarketViewModel:
    """Immutable presentation model for market workspace state."""

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
