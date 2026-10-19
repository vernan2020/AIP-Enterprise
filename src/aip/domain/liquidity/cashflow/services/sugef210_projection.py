"""SUGEF 2-10 projected liquidity ladder, distinct from regulatory IRRBB GAP.

Daily 0..7, weekly 8..30, fixed monthly 31..60 and 61..90,
then quarterly 91..180, 181..270 and 271..365.
No inferred deposit runs, renewal rates, off-balance calls or sight availability.
Every stressed event requires a documented, approved assumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Iterable

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
    financing_need: Decimal | None = None
    asset_outflows: Decimal = Decimal(0)
    liability_inflows: Decimal = Decimal(0)


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
    unattested_areas: tuple[str, ...] = ()
    unattested_opening_currencies: tuple[str, ...] = ()

    @property
    def certified_comprehensive(self) -> bool:
        return self.status == "COMPLETE_GOVERNED_PROJECTION"


def sugef210_windows(cutoff: date) -> tuple[LiquidityWindow, ...]:
    """Contiguous fixed regulatory horizons from day zero through day 365."""
    bands: list[tuple[str, str, int, int, str]] = [
        ("D00", "Hoy · capacidad intradía", 0, 0, "DAILY")
    ]
    for day in range(1, 8):
        bands.append((f"D{day:02}", f"Día {day}", day, day, "DAILY"))
    for first, last in ((8, 14), (15, 21), (22, 28), (29, 30)):
        bands.append(
            (f"W{first:02}_{last:02}", f"Días {first}–{last}", first, last, "WEEKLY")
        )
    bands.extend(
        (
            ("M01", "Días 31–60", 31, 60, "MONTHLY"),
            ("M02", "Días 61–90", 61, 90, "MONTHLY"),
            ("Q01", "Días 91–180", 91, 180, "QUARTERLY"),
            ("Q02", "Días 181–270", 181, 270, "QUARTERLY"),
            ("Q03", "Días 271–365", 271, 365, "QUARTERLY"),
        )
    )
    windows = tuple(
        LiquidityWindow(
            key=key,
            label=label,
            start=cutoff + timedelta(days=first),
            end=cutoff + timedelta(days=last),
            frequency=frequency,
        )
        for key, label, first, last, frequency in bands
    )
    if windows[0].start != cutoff or windows[-1].end != cutoff + timedelta(days=365):
        raise ValueError("Projection must end exactly at day 365")
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
    source_certification_references: dict[LiquidityBalanceArea, str] | None = None,
    opening_certification_references: dict[str, str] | None = None,
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
            asset_out = subtotal(LiquidityBalanceArea.ASSET, LiquidityFlowSide.OUTFLOW)
            liability_in = subtotal(LiquidityBalanceArea.LIABILITY, LiquidityFlowSide.INFLOW)
            liability_out = subtotal(LiquidityBalanceArea.LIABILITY, LiquidityFlowSide.OUTFLOW)
            off_in = subtotal(LiquidityBalanceArea.OFF_BALANCE, LiquidityFlowSide.INFLOW)
            off_out = subtotal(LiquidityBalanceArea.OFF_BALANCE, LiquidityFlowSide.OUTFLOW)
            business_in = subtotal(LiquidityBalanceArea.BUSINESS_EVENT, LiquidityFlowSide.INFLOW)
            business_out = subtotal(LiquidityBalanceArea.BUSINESS_EVENT, LiquidityFlowSide.OUTFLOW)
            net = (
                asset_in + liability_in + off_in + business_in
                - asset_out - liability_out - off_out - business_out
            )
            running += net
            initial = opening.get(currency)
            projected.append(
                LiquidityProjectionRow(
                    window=window, currency=currency,
                    asset_inflows=asset_in, liability_outflows=liability_out,
                    asset_outflows=asset_out, liability_inflows=liability_in,
                    other_inflows=business_in, other_outflows=business_out,
                    off_balance_inflows=off_in, off_balance_outflows=off_out,
                    net_flow=net, accumulated_flow=running,
                    opening_liquidity=initial,
                    projected_liquidity=initial + running if initial is not None else None,
                    event_count=len(included),
                    financing_need=(
                        max(Decimal(0), -(initial + running))
                        if initial is not None else None
                    ),
                )
            )
    missing = tuple(sorted(area.value for area in required - coverage))
    missing_opening = tuple(ccy for ccy in ("CRC", "USD") if ccy not in opening)
    # Area labels alone are not proof. Require distinct, nonblank attestations
    # for all covered sources and independently verified opening balances.
    area_proofs = source_certification_references or {}
    opening_proofs = opening_certification_references or {}
    unattested = tuple(
        sorted(
            area.value for area in required
            if area in coverage and not str(area_proofs.get(area) or "").strip()
        )
    )
    unattested_opening = tuple(
        currency for currency in ("CRC", "USD")
        if currency in opening and not str(opening_proofs.get(currency) or "").strip()
    )
    complete = not (missing or missing_opening or unattested or unattested_opening)
    return LiquidityProjectionResult(
        cutoff=cutoff, scenario=scenario, windows=windows, rows=tuple(projected),
        status="COMPLETE_GOVERNED_PROJECTION" if complete else "PARTIAL_EVIDENCE_NOT_CERTIFIED",
        source_flow_count=len(events), missing_source_areas=missing,
        opening_liquidity_missing=missing_opening, assumption_ids=tuple(sorted(policies)),
        excluded_out_of_horizon=outside,
        off_balance_source_covered=LiquidityBalanceArea.OFF_BALANCE in coverage,
        unattested_areas=unattested,
        unattested_opening_currencies=unattested_opening,
    )
