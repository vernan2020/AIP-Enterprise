from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from aip.domain.portfolio.services.capital_equivalent_rate_service import (
    CapitalEquivalentRateInput,
    CapitalEquivalentRateResult,
    CapitalEquivalentRateService,
)
from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    CapitalExposure,
    ExposureClass,
    PortfolioCapitalConsumptionService,
    PortfolioCapitalResult,
)


@dataclass(frozen=True, slots=True)
class VerifiedCapitalPosition:
    """Audited financial inputs for one position and one portfolio cutoff.

    All monetary values are CRC. A non-CRC title requires explicit FX provenance;
    neither price, book value nor TIR is silently repurposed as a regulatory base.
    The position key distinguishes multiple lots of the same ISIN.
    """

    position_key: str
    isin: str
    issuer: str
    currency: str
    cutoff: date
    invested_amount_crc: Decimal
    regulatory_exposure_crc: Decimal
    annual_net_yield: Decimal
    exposure_class: ExposureClass
    classification_effective_date: date
    invested_amount_source: str
    regulatory_exposure_source: str
    net_yield_source: str
    classification_source: str
    fx_translation_source: str = ""


@dataclass(frozen=True, slots=True)
class AuditedCapitalEvaluation:
    cutoff: date
    portfolio: PortfolioCapitalResult
    equivalent_rates: tuple[CapitalEquivalentRateResult, ...]
    total_invested_crc: Decimal
    annual_equity_charge_crc: Decimal


class PortfolioCapitalEvidenceService:
    """Fail-closed bridge from independently verified records into certified math.

    This module does not fetch a corporate master or validate an institution's
    regulatory returns. It requires a dated, auditable feed from that adapter.
    """

    @staticmethod
    def validate(
        positions: Sequence[VerifiedCapitalPosition], *, cutoff: date
    ) -> tuple[VerifiedCapitalPosition, ...]:
        records = tuple(positions)
        if not records:
            raise ValueError("No audited capital evidence supplied")
        seen: set[str] = set()
        for row in records:
            if row.cutoff != cutoff:
                raise ValueError("Capital evidence cutoff does not match portfolio cutoff")
            if row.classification_effective_date > cutoff:
                raise ValueError("Future-dated regulatory classification is not valid")
            if not row.position_key.strip() or row.position_key in seen:
                raise ValueError("Position keys must be present and unique per cutoff")
            seen.add(row.position_key)
            if not row.isin.strip() or not row.issuer.strip():
                raise ValueError("ISIN and issuer are required for capital audit")
            if not row.currency.strip() or len(row.currency.strip()) != 3:
                raise ValueError("Portfolio currency must be a three-letter code")
            for value in (
                row.invested_amount_crc,
                row.regulatory_exposure_crc,
                row.annual_net_yield,
            ):
                if not isinstance(value, Decimal) or not value.is_finite():
                    raise ValueError("Audited capital values must be finite Decimal quantities")
            if row.invested_amount_crc <= 0 or row.regulatory_exposure_crc < 0:
                raise ValueError("Invested amount must be positive and exposure non-negative")
            if not all(
                source.strip()
                for source in (
                    row.invested_amount_source,
                    row.regulatory_exposure_source,
                    row.net_yield_source,
                    row.classification_source,
                )
            ):
                raise ValueError("All capital inputs require explicit audit source references")
            if row.currency.strip().upper() != "CRC" and not row.fx_translation_source.strip():
                raise ValueError("Foreign-currency position requires audited FX translation source")
            # Reuse the portfolio domain's sovereign/currency and class validation.
            PortfolioCapitalConsumptionService.evaluate(
                (
                    CapitalExposure(
                        security_key=row.position_key,
                        issuer=row.issuer,
                        currency=row.currency.strip().upper(),
                        regulatory_exposure_crc=row.regulatory_exposure_crc,
                        exposure_class=row.exposure_class,
                        classification_source=row.classification_source,
                    ),
                )
            )
        return records

    @staticmethod
    def evaluate(
        positions: Sequence[VerifiedCapitalPosition],
        *,
        cutoff: date,
        annual_cost_of_equity: Decimal,
        target_capital_adequacy: Decimal = Decimal("0.16"),
    ) -> AuditedCapitalEvaluation:
        records = PortfolioCapitalEvidenceService.validate(positions, cutoff=cutoff)
        # The cost is mandatory and must be provided by the user, never defaulted.
        equivalents = tuple(
            CapitalEquivalentRateService.calculate(
                CapitalEquivalentRateInput(
                    invested_amount_crc=row.invested_amount_crc,
                    regulatory_exposure_crc=row.regulatory_exposure_crc,
                    annual_net_yield=row.annual_net_yield,
                    annual_cost_of_equity=annual_cost_of_equity,
                    exposure_class=row.exposure_class,
                    target_capital_adequacy=target_capital_adequacy,
                )
            )
            for row in records
        )
        portfolio = PortfolioCapitalConsumptionService.evaluate(
            tuple(
                CapitalExposure(
                    security_key=row.position_key,
                    issuer=row.issuer,
                    currency=row.currency.strip().upper(),
                    regulatory_exposure_crc=row.regulatory_exposure_crc,
                    exposure_class=row.exposure_class,
                    classification_source=row.classification_source,
                )
                for row in records
            )
        )
        return AuditedCapitalEvaluation(
            cutoff=cutoff,
            portfolio=portfolio,
            equivalent_rates=equivalents,
            total_invested_crc=sum((row.invested_amount_crc for row in records), Decimal("0")),
            annual_equity_charge_crc=sum(
                (result.annual_equity_charge_crc for result in equivalents), Decimal("0")
            ),
        )
