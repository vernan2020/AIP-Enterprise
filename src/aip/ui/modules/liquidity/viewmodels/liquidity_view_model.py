from __future__ import annotations

from dataclasses import asdict, dataclass, field

from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow


@dataclass(frozen=True, slots=True)
class LiquidityViewModel:
    """Immutable presentation model for the liquidity workspace."""

    summary: object
    cashflow_rows: tuple[LiquidityRow, ...]
    gap_rows: tuple[LiquidityRow, ...]
    hqla_rows: tuple[LiquidityRow, ...]
    mil_rows: tuple[LiquidityRow, ...]
    stress_rows: tuple[LiquidityRow, ...]
    filters: dict[str, str] = field(default_factory=dict)
    selected_section: str | None = None
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
            "cashflow_rows": [asdict(row) for row in self.cashflow_rows],
            "gap_rows": [asdict(row) for row in self.gap_rows],
            "hqla_rows": [asdict(row) for row in self.hqla_rows],
            "mil_rows": [asdict(row) for row in self.mil_rows],
            "stress_rows": [asdict(row) for row in self.stress_rows],
            "filters": dict(self.filters),
            "selected_section": self.selected_section,
            "theme": self.theme,
            "status": self.status,
            "warnings": list(self.warnings),
            "calculation_id": self.calculation_id,
            "correlation_id": self.correlation_id,
            "loading": self.loading,
            "error": self.error,
        }
