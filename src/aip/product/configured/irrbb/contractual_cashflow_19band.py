"""Audited nineteen-band aggregation of canonical, source-evidenced cash flows.

This read-only component never invents amortizations, repricing residuals,
contractual interest, behavioral deposits, or an EVE/NII certification.
It preserves currencies and banking-book sides without FX conversion.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowAmountStatus,
    IRRBBCashFlow,
    IRRBBTimeBucket,
)
from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
from aip.shared.money import Currency

ALLOWED_AMOUNTS = frozenset(
    (CashFlowAmountStatus.CONTRACTUAL, CashFlowAmountStatus.SOURCE_PROVIDED)
)
REQUIRED_SEGMENTS = frozenset(("CREDIT", "INVESTMENT", "CAPTACIONES", "BORROWING"))


@dataclass(frozen=True, slots=True)
class EvidencedFlow:
    segment: str
    cashflow: IRRBBCashFlow
    validation_reference: str

    def __post_init__(self) -> None:
        if self.segment not in REQUIRED_SEGMENTS:
            raise ValueError("Unrecognized segment in 19-band cashflow evidence")
        if not self.validation_reference.strip():
            raise ValueError("Cashflow schedule validation evidence is required")
        if self.segment in {"CREDIT", "INVESTMENT"} and (
            self.cashflow.side is not BankingBookSide.ASSET
        ):
            raise ValueError("Asset segment has incompatible banking-book side")
        if self.segment in {"CAPTACIONES", "BORROWING"} and (
            self.cashflow.side is not BankingBookSide.LIABILITY
        ):
            raise ValueError("Liability segment has incompatible banking-book side")


@dataclass(frozen=True, slots=True)
class NineteenBandEvidenceRow:
    currency: Currency
    ordinal: int
    bucket: IRRBBTimeBucket
    label: str
    assets: Decimal
    liabilities: Decimal
    net: Decimal
    flow_count: int


@dataclass(frozen=True, slots=True)
class Contractual19BandEvidenceResult:
    cutoff_date: date
    rows: tuple[NineteenBandEvidenceRow, ...]
    total_flows: int
    included_segments: tuple[str, ...]
    missing_segments: tuple[str, ...]
    status: str = "CONTRACTUAL_CASHFLOW_EVIDENCE_NOT_CERTIFIED"

    @property
    def publishable_regulatory_gap(self) -> bool:
        return False


class Contractual19BandEvidenceAggregator:
    """Assign proven dated canonical flows; fail closed on insufficient evidence."""

    def aggregate(
        self,
        *,
        cutoff_date: date,
        flows: Iterable[EvidencedFlow],
    ) -> Contractual19BandEvidenceResult:
        amounts: dict[tuple[Currency, int, BankingBookSide], Decimal] = defaultdict(Decimal)
        counts: dict[tuple[Currency, int], int] = defaultdict(int)
        seen: set[tuple[str, str, date, date, str, Decimal, str]] = set()
        currencies: set[Currency] = set()
        segments: set[str] = set()
        count = 0
        for item in flows:
            event = item.cashflow
            if event.amount_status not in ALLOWED_AMOUNTS:
                raise ValueError("Uncertified derived or behavioral flow cannot enter evidence")
            if not event.amount.amount.is_finite() or event.amount.amount < 0:
                raise ValueError("Contractual flow amount must be finite and non-negative")
            if event.cashflow_date < cutoff_date or event.risk_date < cutoff_date:
                raise ValueError("Historical cashflow or repricing date cannot be assigned")
            if event.risk_date > event.cashflow_date:
                raise ValueError("Risk date cannot be after its contractual payment date")
            event_key = (
                item.segment,
                event.position_id,
                event.cashflow_date,
                event.risk_date,
                event.flow_type,
                event.amount.amount,
                event.source_reference,
            )
            if event_key in seen:
                raise ValueError("Duplicate contractual source cashflow")
            seen.add(event_key)
            assigned = IRRBBTimeBucketService.assign(
                valuation_date=cutoff_date,
                risk_date=event.risk_date,
            )
            currency = event.amount.currency
            amounts[(currency, assigned.ordinal, event.side)] += event.amount.amount
            counts[(currency, assigned.ordinal)] += 1
            currencies.add(currency)
            segments.add(item.segment)
            count += 1

        # The canonical service defines every ordinal even if no observed flow
        # occupies that band. Present complete 19-row matrices for each currency.
        columns = [
            (1, IRRBBTimeBucket.DAY_1, "Overnight"),
            *[
                (ordinal, bucket, label)
                for ordinal, (_months, bucket, label) in enumerate(
                    IRRBBTimeBucketService._MONTH_BUCKETS, start=2
                )
            ],
            (19, IRRBBTimeBucket.OVER_YEAR_20, "Más de 20 años"),
        ]
        rows: list[NineteenBandEvidenceRow] = []
        for currency in sorted(currencies, key=lambda value: value.value):
            for ordinal, bucket, label in columns:
                assets = amounts[(currency, ordinal, BankingBookSide.ASSET)]
                liabilities = amounts[(currency, ordinal, BankingBookSide.LIABILITY)]
                rows.append(
                    NineteenBandEvidenceRow(
                        currency=currency,
                        ordinal=ordinal,
                        bucket=bucket,
                        label=label,
                        assets=assets,
                        liabilities=liabilities,
                        net=assets - liabilities,
                        flow_count=counts[(currency, ordinal)],
                    )
                )
        if sum(row.flow_count for row in rows) != count:
            raise ValueError("Contractual flows were not fully reconciled in 19 bands")
        return Contractual19BandEvidenceResult(
            cutoff_date=cutoff_date,
            rows=tuple(rows),
            total_flows=count,
            included_segments=tuple(sorted(segments)),
            missing_segments=tuple(sorted(REQUIRED_SEGMENTS - segments)),
        )

