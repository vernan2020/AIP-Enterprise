from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    PortfolioCapitalEvidenceService,
    VerifiedCapitalPosition,
)


@dataclass(frozen=True, slots=True)
class CapitalBreakdownGroup:
    dimension: str
    label: str
    position_count: int
    invested_amount_crc: Decimal
    regulatory_exposure_crc: Decimal
    credit_rwa_crc: Decimal
    target_equity_crc: Decimal
    annual_equity_charge_crc: Decimal
    annual_net_income_before_equity_cost_crc: Decimal
    weighted_net_yield_before_equity_cost: Decimal
    weighted_net_yield_after_equity_cost: Decimal
    classification_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapitalPortfolioBreakdown:
    """Economic consumption for a traceable portfolio cutoff, not official SP."""

    cutoff: date
    total_positions: int
    total_invested_crc: Decimal
    total_regulatory_exposure_crc: Decimal
    total_credit_rwa_crc: Decimal
    weighted_risk_weight: Decimal
    target_equity_crc: Decimal
    annual_equity_charge_crc: Decimal
    weighted_net_yield_before_equity_cost: Decimal
    weighted_net_yield_after_equity_cost: Decimal
    by_issuer: tuple[CapitalBreakdownGroup, ...]
    by_currency: tuple[CapitalBreakdownGroup, ...]
    by_exposure_class: tuple[CapitalBreakdownGroup, ...]


class PortfolioCapitalBreakdownService:
    """Aggregate independently sourced capital records with no implicit bases.

    The mandatory editable cost of equity is applied consistently to each
    position and each group. Regulatory exposure is never inferred from market
    value, book value or the face amount of a security.
    """

    @staticmethod
    def calculate(
        positions: Sequence[VerifiedCapitalPosition],
        *,
        cutoff: date,
        annual_cost_of_equity: Decimal,
        target_capital_adequacy: Decimal = Decimal("0.16"),
    ) -> CapitalPortfolioBreakdown:
        records = tuple(positions)
        evaluated = PortfolioCapitalEvidenceService.evaluate(
            records,
            cutoff=cutoff,
            annual_cost_of_equity=annual_cost_of_equity,
            target_capital_adequacy=target_capital_adequacy,
        )
        if len(records) != len(evaluated.portfolio.items):
            raise ValueError("Position and capital results must align")
        before = sum(
            (row.invested_amount_crc * row.annual_net_yield for row in records),
            Decimal("0"),
        )
        invested = evaluated.total_invested_crc

        def group_by(dimension: str) -> tuple[CapitalBreakdownGroup, ...]:
            def key(row: VerifiedCapitalPosition) -> str:
                if dimension == "issuer":
                    return row.issuer.strip()
                if dimension == "currency":
                    return row.currency.strip().upper()
                return row.exposure_class.value

            buckets: dict[str, list[int]] = {}
            for index, row in enumerate(records):
                buckets.setdefault(key(row), []).append(index)

            groups: list[CapitalBreakdownGroup] = []
            for label, indices in sorted(buckets.items()):
                base = sum((records[i].invested_amount_crc for i in indices), Decimal("0"))
                exposure = sum(
                    (records[i].regulatory_exposure_crc for i in indices), Decimal("0")
                )
                rwa = sum(
                    (evaluated.portfolio.items[i].credit_rwa_crc for i in indices), Decimal("0")
                )
                equity = sum(
                    (evaluated.equivalent_rates[i].required_capital_crc for i in indices),
                    Decimal("0"),
                )
                annual_charge = sum(
                    (evaluated.equivalent_rates[i].annual_equity_charge_crc for i in indices),
                    Decimal("0"),
                )
                income = sum(
                    (records[i].invested_amount_crc * records[i].annual_net_yield for i in indices),
                    Decimal("0"),
                )
                groups.append(
                    CapitalBreakdownGroup(
                        dimension=dimension,
                        label=label,
                        position_count=len(indices),
                        invested_amount_crc=base,
                        regulatory_exposure_crc=exposure,
                        credit_rwa_crc=rwa,
                        target_equity_crc=equity,
                        annual_equity_charge_crc=annual_charge,
                        annual_net_income_before_equity_cost_crc=income,
                        weighted_net_yield_before_equity_cost=income / base,
                        weighted_net_yield_after_equity_cost=(income - annual_charge) / base,
                        classification_sources=tuple(
                            sorted({records[i].classification_source.strip() for i in indices})
                        ),
                    )
                )
            return tuple(groups)

        return CapitalPortfolioBreakdown(
            cutoff=cutoff,
            total_positions=len(records),
            total_invested_crc=invested,
            total_regulatory_exposure_crc=evaluated.portfolio.total_regulatory_exposure_crc,
            total_credit_rwa_crc=evaluated.portfolio.total_credit_rwa_crc,
            weighted_risk_weight=evaluated.portfolio.weighted_average_risk_weight,
            target_equity_crc=evaluated.portfolio.total_credit_rwa_crc * target_capital_adequacy,
            annual_equity_charge_crc=evaluated.annual_equity_charge_crc,
            weighted_net_yield_before_equity_cost=before / invested,
            weighted_net_yield_after_equity_cost=(
                before - evaluated.annual_equity_charge_crc
            ) / invested,
            by_issuer=group_by("issuer"),
            by_currency=group_by("currency"),
            by_exposure_class=group_by("exposure_class"),
        )
