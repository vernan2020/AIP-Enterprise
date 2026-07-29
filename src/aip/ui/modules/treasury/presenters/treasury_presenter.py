from __future__ import annotations

from typing import Any

from aip.ui.modules.treasury.models.treasury_row import TreasuryRow
from aip.ui.modules.treasury.viewmodels.treasury_view_model import TreasuryViewModel


class TreasuryPresenter:
    """Presenter that adapts treasury context into a passive view model."""

    def __init__(self, orchestrator: Any | None = None) -> None:
        self._orchestrator = orchestrator

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, loading: bool = False, error: str | None = None) -> TreasuryViewModel:
        rows = (
            TreasuryRow(title="Cash buffer review", detail="Increase short-term cash buffer by 2.5%", severity="High", source="Treasury Ops", timestamp="2026-07-29"),
            TreasuryRow(title="Funding window", detail="Reprice term funding before next rollover", severity="Medium", source="Funding Desk", timestamp="2026-07-29"),
        )
        summary = (
            "Treasury coverage: 98%",
            "Liquidity buffer: Healthy",
            "Policy posture: Stable",
        )
        return TreasuryViewModel(
            summary=summary,
            recommendations=rows,
            alerts=(TreasuryRow(title="Alert", detail="Near-term cash requirement is elevated", severity="High", source="Cash Management", timestamp="2026-07-29"),),
            opportunities=(TreasuryRow(title="Opportunity", detail="Capture favorable term deposit rates", severity="Medium", source="Markets", timestamp="2026-07-29"),),
            filters=filters or {},
            theme_name=theme,
            status="loaded" if not error else "error",
            loading=loading,
            error=error,
        )

    def refresh(self, *, theme: str = "light", filters: dict[str, str] | None = None) -> TreasuryViewModel:
        return self.build_view_model(theme=theme, filters=filters)

    def handle_theme_change(self, theme: str) -> TreasuryViewModel:
        return self.build_view_model(theme=theme)

    def handle_refresh(self) -> TreasuryViewModel:
        return self.build_view_model()

    def apply_filters(self, filters: dict[str, str]) -> TreasuryViewModel:
        return self.build_view_model(filters=filters)

    def handle_application_failure(self, error: str) -> TreasuryViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> TreasuryViewModel:
        return self.build_view_model(loading=True)
