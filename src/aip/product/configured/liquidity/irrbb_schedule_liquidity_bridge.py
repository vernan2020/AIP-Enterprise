"""Reuse exclusively certified, DATED IRRBB source schedules for liquidity.

Cashflow date, not IRRBB repricing/risk date, drives the liquidity horizon.
Does not adapt regulatory six-band gaps, maturity-only inventory or modeled
variable-rate/behavioral positions. Off-balance coverage remains independent.
"""

from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.models import BankingBookSide, CashFlowDirection
from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.irrbb.four_source_19band_consolidation import (
    ConsolidatedSourceEvidence,
)


@dataclass(frozen=True, slots=True)
class LiquiditySourceBridgeResult:
    cashflows: tuple[LiquidityProjectionFlow, ...]
    covered_balance_areas: frozenset[LiquidityBalanceArea]
    source_status: str


def adapt_certified_irrbb_schedule(
    evidence: ConsolidatedSourceEvidence,
) -> LiquiditySourceBridgeResult:
    """Retain every source-provided principal/interest event; no inferred coupons."""
    if evidence.status != "FOUR_SOURCE_FIXED_SCHEDULE_EVIDENCE_NOT_CERTIFIED_GAP":
        raise ValueError("Unexpected IRRBB contractual evidence status")
    if evidence.evidence.missing_segments:
        raise ValueError("IRRBB source schedules missing one or more balance segments")
    events: list[LiquidityProjectionFlow] = []
    for flow in evidence.flows:
        source = flow.cashflow
        if source.risk_date != source.cashflow_date:
            raise ValueError("Repricing and cash receipt dates differ; no liquidity inference")
        if source.flow_type.strip().upper() not in {"PRINCIPAL", "INTEREST", "COUPON"}:
            raise ValueError("Unknown source cashflow type")
        area = (
            LiquidityBalanceArea.ASSET
            if flow.segment in {"CREDIT", "INVESTMENT"}
            else LiquidityBalanceArea.LIABILITY
        )
        if (
            area == LiquidityBalanceArea.ASSET
            and (source.side != BankingBookSide.ASSET or source.direction != CashFlowDirection.RECEIVABLE)
        ) or (
            area == LiquidityBalanceArea.LIABILITY
            and (source.side != BankingBookSide.LIABILITY or source.direction != CashFlowDirection.PAYABLE)
        ):
            raise ValueError("Inconsistent contractual source and liquidity direction")
        events.append(
            LiquidityProjectionFlow(
                reference=(
                    f"{flow.segment}:{source.position_id}:"
                    f"{source.source_reference}:{source.cashflow_date.isoformat()}:"
                    f"{source.flow_type.upper()}"
                ),
                source=f"RTILB_GOVERNED_SCHEDULE:{flow.validation_reference}",
                currency=source.amount.currency.value,
                payment_date=source.cashflow_date,
                amount=source.amount.amount,
                side=(
                    LiquidityFlowSide.INFLOW
                    if area == LiquidityBalanceArea.ASSET
                    else LiquidityFlowSide.OUTFLOW
                ),
                area=area,
                evidence=LiquidityEvidence.CONTRACTUAL,
            )
        )
    return LiquiditySourceBridgeResult(
        cashflows=tuple(events),
        covered_balance_areas=frozenset(
            {LiquidityBalanceArea.ASSET, LiquidityBalanceArea.LIABILITY}
        ),
        source_status="CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED",
    )
