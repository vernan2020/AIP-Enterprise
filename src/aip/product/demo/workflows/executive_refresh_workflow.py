from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.demo.configuration.demo_config import DemoConfig


class ExecutiveRefreshWorkflow:
    """Creates executive-level refresh output for the demo UI."""

    def __init__(
        self,
        config: DemoConfig,
        valuation_date_context: ValuationDateContext | None = None,
    ) -> None:
        self._config = config
        self._valuation_date_context = valuation_date_context

    def execute(self, correlation_id: str) -> dict[str, Any]:
        return {
            "execution_id": f"executive-{correlation_id}",
            "correlation_id": correlation_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": "READY",
            "mode": self._config.execution_mode,
            "valuation_date": (
                self._valuation_date_context.value
                if self._valuation_date_context is not None
                else self._config.data_cutoff_date
            ).isoformat(),
            "calculation_id": "calc-executive-demo",
        }
