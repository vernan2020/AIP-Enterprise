from __future__ import annotations

from dataclasses import dataclass, field

from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow


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

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary.__dict__ if hasattr(self.summary, "__dict__") else {},
            "rows": [row.__dict__ for row in self.rows],
            "curve_points": [curve.__dict__ for curve in self.curve_points],
            "filters": dict(self.filters),
            "selected_curve": self.selected_curve,
            "theme": self.theme,
            "status": self.status,
            "warnings": list(self.warnings),
            "calculation_id": self.calculation_id,
            "correlation_id": self.correlation_id,
            "loading": self.loading,
            "error": self.error,
        }
