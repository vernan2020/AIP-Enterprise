from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from aip.application.exceptions import ContractValidationError
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.base.financial_instrument import FinancialInstrument


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """Application-level request for domain analysis workflows."""

    workflow_id: str
    correlation_id: str
    valuation_date: date
    instrument: FinancialInstrument
    market_yield: Decimal
    curve: YieldCurve | None = None
    market_price: Decimal | None = None
    benchmark_yield: Decimal | None = None
    calculation_id: str | None = None
    requested_at: datetime | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workflow_id or not str(self.workflow_id).strip():
            raise ContractValidationError("workflow_id is required")
        if not self.correlation_id or not str(self.correlation_id).strip():
            raise ContractValidationError("correlation_id is required")
        if self.requested_at is not None and self.requested_at.tzinfo is None:
            raise ContractValidationError("requested_at must be timezone-aware")
        if self.requested_at is None:
            object.__setattr__(self, "requested_at", datetime.now(UTC))
        if self.context is None:
            object.__setattr__(self, "context", {})
        else:
            object.__setattr__(self, "context", deepcopy(dict(self.context)))
        if self.calculation_id is None and self.context.get("deterministic_ids", False):
            object.__setattr__(self, "calculation_id", f"{self.workflow_id}:{self.correlation_id}")
