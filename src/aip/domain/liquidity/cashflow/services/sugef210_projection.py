"""SUGEF 2-10 projected liquidity ladder, distinct from regulatory IRRBB GAP.

Daily 0..7, weekly 8..30, two calendar-month windows and quarterly to one year.
No inferred deposit runs, renewal rates, off-balance calls or sight availability.
Every stressed event requires a documented, approved assumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Iterable

from dateutil.relativedelta import relativedelta


class LiquidityFlowSide(str, Enum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"


class LiquidityBalanceArea(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    OFF_BALANCE = "OFF_BALANCE"
    BUSINESS_EVENT = "BUSINESS_EVENT"


class LiquidityEvidence(str, Enum):
    CONTRACTUAL = "CONTRACTUAL"
    GOVERNED_ASSUMPTION = "GOVERNED_ASSUMPTION"


@dataclass(frozen=True, slots=True)
class LiquidityProjectionFlow:
    reference: str
    source: str
    currency: str
    payment_date: date
    amount: Decimal
    side: LiquidityFlowSide
    area: LiquidityBalanceArea
    evidence: LiquidityEvidence
    assumption_id: str | None = None

    def __post_init__(self) -> None:
        if not self.reference or not self.source:
            raise ValueError("Liquidity event requires source and unique reference")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError("Liquidity currency must be explicitly CRC or USD")
        if not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("Liquidity flow amount must be finite and positive")
        if self.evidence == LiquidityEvidence.GOVERNED_ASSUMPTION and not self.assumption_id:
            raise ValueError("Noncontractual events require a documented assumption ID")
        if self.evidence == LiquidityEvidence.CONTRACTUAL and self.assumption_id:
            raise ValueError("Contractual events cannot mask embedded assumptions")


@dataclass(frozen=True, slots=True)
class LiquidityAssumption:
    assumption_id: str
    rationale: str
    approval_reference: str
    valid_from: date
    valid_to: date
    source_reference: str
    scenario: str

    def __post_init__(self) -> None:
        if not all(
            (self.assumption_id, self.rationale, self.approval_reference,
             self.source_reference, self.scenario)
        ):
            raise ValueError("Assumption requires rationale, approval, source and scenario")
        if self.valid_from > self.valid_to:
            raise ValueError("Assumption validity interval is inverted")


@dataclass(frozen=True, slots=True)
class LiquidityWindow:
    key: str
    label: str
    start: date
    end: date
    frequency: str


@dataclass(frozen=True, slots=True)
class LiquidityProjectionRow:
    window: LiquidityWindow
    currency: str
    asset_inflows: Decimal
    liability_outflows: Decimal
    other_inflows: Decimal
    other_outflows: Decimal
    off_balance_inflows: Decimal
    off_balance_outflows: Decimal
    net_flow: Decimal
    accumulated_flow: Decimal
    opening_liquidity: Decimal | None
    projected_liquidity: Decimal | None
    event_count: int


@dataclass(frozen=True, slots=True)
class LiquidityProjectionResult:
    cutoff: date
    scenario: str
    windows: tuple[LiquidityWindow, ...]
    rows: tuple[LiquidityProjectionRow, ...]
    status: str
    source_flow_count: int
    missing_source_areas: tuple[str, ...]
    opening_liquidity_missing: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    excluded_out_of_horizon: int
    off_balance_source_covered: bool

    @property
    def certified_comprehensive(self) -> bool:
        return self.status == "COMPLETE_GOVERNED_PROJECTION"


def sugef210_windows(cutoff: date) -> tuple[LiquidityWindow, ...]:
    """Non-overlapping, contiguous through one calendar year; day zero is today."""
    intervals: list[tuple[str, str, date, date, str]] = []
    intervals.append(("D00", "Hoy · capacidad intradía", cutoff, cutoff, "DAILY"))
    for day in range(1, 8):
        target = cutoff + timedelta(days=day)
        intervals.append((f"D{day:02}", f"Día {day}", target, target, "DAILY"))
    for first, last in ((8, 14), (15, 21), (22, 28), (29, 30)):
        intervals.append((
            f"W{first:02}_{last:02}", f"Días {first}–{last}",
            cutoff + timedelta(days=first),
            cutoff + timedelta(days=last), "WEEKLY"
        ))
    # Following two rolling CALENDAR months start after the first 30 days.
    boundaries = (cutoff + timedelta(days=30), cutoff + relativedelta(months=2),
                  cutoff + relativedelta(months=3),
                  cutoff + relativedelta(months=6),
                  cutoff + relativedelta(months=9),
                  cutoff + relativedelta(months=12))
    if boundaries[1] <= boundaries[0]:
        raise ValueError("Invalid calendar monthly boundary at cutoff")
    for idx, (first, last) in enumerate(zip(boundaries, boundaries[1:]), 1):
        freq = "MONTHLY" if idx <= 2 else "QUARTERLY"
        intervals.append((
            f"M{idx:02}" if idx <= 2 else f"Q{idx-2:02}",
            f"Mes {idx}" if idx <= 2 else f"Trimestre {idx-2}",
            first + timedelta(days=1), last, freq
        ))
    windows = tuple(LiquidityWindow(*values) for values in intervals)
    if windows[0].start != cutoff or windows[-1].end != cutoff + relativedelta(years=1):
        raise ValueError("Projection year boundaries not reconciled")
    for previous, next_window in zip(windows, windows[1:]):
        if next_window.start != previous.end + timedelta(days=1):
            raise ValueError("Projected liquidity horizon contains overlap or gap")
    return windows


def project_sugef210(
    *,
    cutoff: date,
    scenario: str,
    flows: Iterable[LiquidityProjectionFlow],
    opening_liquidity: dict[str, Decimal] | None,
    assumptions: Iterable[LiquidityAssumption] = (),
    source_areas_covered: Iterable[LiquidityBalanceArea] = (),
) -> LiquidityProjectionResult:
    """Project without numerical substitution for missing institutional sources.

    Opening liquidity must be confirmed independently of the flow event stream.
    The projected balance is unknown when the opening amount is unavailable.
    """
    events = tuple(flows)
    governed = tuple(assumptions)
    if not scenario.strip():
        raise ValueError("A named scenario is mandatory")
    policies: dict[str, LiquidityAssumption] = {}
    for policy in governed:
        if policy.assumption_id in policies:
            raise ValueError("Duplicate liquidity assumption ID")
        policies[policy.assumption_id] = policy
    seen: set[str] = set()
    areas: set[LiquidityBalanceArea] = set()
    for event in events:
        if event.reference in seen:
            raise ValueError("Duplicate liquidity event (risk of double counting)")
        seen.add(event.reference)
        areas.add(event.area)
        if event.payment_date < cutoff:
            raise ValueError("Historical flow cannot be rolled forward to day zero")
        if event.evidence == LiquidityEvidence.GOVERNED_ASSUMPTION:
            policy = policies.get(event.assumption_id or "")
            if policy is None or policy.scenario != scenario:
                raise ValueError("Assumption missing or approved for a different scenario")
            if not policy.valid_from <= cutoff <= policy.valid_to:
                raise ValueError("Liquidity assumption is outside approval validity")
        if event.area == LiquidityBalanceArea.ASSET and event.side != LiquidityFlowSide.INFLOW:
            raise ValueError("Asset cash flows must be recorded as inflows")
        if event.area == LiquidityBalanceArea.LIABILITY and event.side != LiquidityFlowSide.OUTFLOW:
            raise ValueError("Liability cash flows must be recorded as outflows")

    opening = dict(opening_liquidity or {})
    for currency, amount in opening.items():
        if currency not in {"CRC", "USD"} or not amount.is_finite() or amount < 0:
            raise ValueError("Opening liquidity must be valid and currency-specific")
    coverage = set(source_areas_covered)
    if not coverage.issubset(set(LiquidityBalanceArea)):
        raise ValueError("Unknown source coverage area")
    required = {LiquidityBalanceArea.ASSET, LiquidityBalanceArea.LIABILITY,
                LiquidityBalanceArea.OFF_BALANCE, LiquidityBalanceArea.BUSINESS_EVENT}
    windows = sugef210_windows(cutoff)
    horizon_end = windows[-1].end
    projected: list[LiquidityProjectionRow] = []
    outside = sum(e.payment_date > horizon_end for e in events)
    # Both supported currencies are kept separate even if source has no events.
    for currency in ("CRC", "USD"):
        running = Decimal(0)
        for window in windows:
            included = tuple(
                e for e in events
                if e.currency == currency and window.start <= e.payment_date <= window.end
            )
            def subtotal(area: LiquidityBalanceArea, side: LiquidityFlowSide) -> Decimal:
                return sum(
                    (e.amount for e in included if e.area == area and e.side == side),
                    Decimal(0)
                )
            asset_in = subtotal(LiquidityBalanceArea.ASSET, LiquidityFlowSide.INFLOW)
            liability_out = subtotal(LiquidityBalanceArea.LIABILITY, LiquidityFlowSide.OUTFLOW)
            off_in = subtotal(LiquidityBalanceArea.OFF_BALANCE, LiquidityFlowSide.INFLOW)
            off_out = subtotal(LiquidityBalanceArea.OFF_BALANCE, LiquidityFlowSide.OUTFLOW)
            business_in = subtotal(LiquidityBalanceArea.BUSINESS_EVENT, LiquidityFlowSide.INFLOW)
            business_out = subtotal(LiquidityBalanceArea.BUSINESS_EVENT, LiquidityFlowSide.OUTFLOW)
            net = asset_in + off_in + business_in - liability_out - off_out - business_out
            running += net
            initial = opening.get(currency)
            projected.append(
                LiquidityProjectionRow(
                    window=window, currency=currency,
                    asset_inflows=asset_in, liability_outflows=liability_out,
                    other_inflows=business_in, other_outflows=business_out,
                    off_balance_inflows=off_in, off_balance_outflows=off_out,
                    net_flow=net, accumulated_flow=running,
                    opening_liquidity=initial,
                    projected_liquidity=initial + running if initial is not None else None,
                    event_count=len(included),
                )
            )
    missing = tuple(sorted(area.value for area in required - coverage))
    missing_opening = tuple(ccy for ccy in ("CRC", "USD") if ccy not in opening)
    # Structural full coverage must be asserted by adapter after source checks,
    # never inferred from transactions merely being present.
    complete = not missing and not missing_opening
    return LiquidityProjectionResult(
        cutoff=cutoff, scenario=scenario, windows=windows, rows=tuple(projected),
        status="COMPLETE_GOVERNED_PROJECTION" if complete else "PARTIAL_EVIDENCE_NOT_CERTIFIED",
        source_flow_count=len(events), missing_source_areas=missing,
        opening_liquidity_missing=missing_opening, assumption_ids=tuple(sorted(policies)),
        excluded_out_of_horizon=outside,
        off_balance_source_covered=LiquidityBalanceArea.OFF_BALANCE in coverage,
    )
