from __future__ import annotations

from datetime import date, datetime
from typing import Any

from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.macro_intelligence.viewmodels.macro_intelligence_view_model import (
    MacroProjectionRow,
    MacroProjectionViewModel,
)


class MacroIntelligencePresenter:
    """Presentation adapter for the governed institutional macro projection."""

    def __init__(self, application_factory: DemoApplicationFactory) -> None:
        self._application_factory = application_factory

    @staticmethod
    def _date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def build_projection(self) -> MacroProjectionViewModel:
        try:
            service = self._application_factory.container.resolve(
                ConfiguredMacroIntelligenceService
            )
            payload: dict[str, Any] = service.get_projection()
        except Exception as exc:
            return MacroProjectionViewModel(
                status="ERROR",
                diagnostic=f"{type(exc).__name__}: {exc}",
            )

        if str(payload.get("status") or "").upper() != "AVAILABLE":
            return MacroProjectionViewModel(
                status=str(payload.get("status") or "UNAVAILABLE"),
                scenario_id=str(payload.get("scenario_id") or "-"),
                diagnostic=str(payload.get("diagnostic") or "Projection unavailable"),
            )

        rows: list[MacroProjectionRow] = []
        for raw in payload.get("rows", ()):
            if not isinstance(raw, dict):
                continue
            period = self._date(raw.get("period"))
            if period is None:
                continue
            rows.append(
                MacroProjectionRow(
                    period=period,
                    fx_sell=self._float(raw.get("fx_sell")),
                    tpm=self._float(raw.get("tpm")),
                    tbp=self._float(raw.get("tbp")),
                    tri_crc_12m=self._float(raw.get("tri_crc_12m")),
                    tri_usd_12m=self._float(raw.get("tri_usd_12m")),
                    inflation=self._float(raw.get("inflation")),
                    imae=self._float(raw.get("imae")),
                )
            )

        rows.sort(key=lambda item: item.period)
        return MacroProjectionViewModel(
            status="AVAILABLE",
            scenario_id=str(payload.get("scenario_id") or "-"),
            version=int(payload.get("version") or 0),
            scenario_type=str(payload.get("scenario_type") or "-"),
            scenario_status=str(payload.get("scenario_status") or "-"),
            dataset_as_of_date=self._date(payload.get("dataset_as_of_date")),
            horizon=int(payload.get("horizon") or len(rows)),
            rows=tuple(rows),
        )
