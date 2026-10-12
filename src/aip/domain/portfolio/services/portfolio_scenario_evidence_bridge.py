from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    CapitalExposure,
    PortfolioCapitalConsumptionService,
)
from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    PortfolioCapitalEvidenceService,
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import (
    PortfolioScenarioRiskService,
    ScenarioRiskComparison,
    ScenarioRiskPolicy,
    VerifiedScenarioRiskAsset,
)


@dataclass(frozen=True, slots=True)
class VerifiedPositionMarketRisk:
    """CRC market and risk amounts from independent providers at one cutoff."""

    position_key: str
    cutoff: date
    market_value_crc: Decimal
    modified_duration_years: Decimal
    dv01_crc: Decimal
    eligible_hqla_value_crc: Decimal
    market_value_source: str
    duration_source: str
    dv01_source: str
    hqla_source: str


@dataclass(frozen=True, slots=True)
class AuditedPortfolioScenario:
    """Reconciled weight scenario, not an executable or priced trading plan."""

    comparison: ScenarioRiskComparison
    position_keys: tuple[str, ...]
    current_weights: tuple[Decimal, ...]
    proposed_weights: tuple[Decimal, ...]
    regulatory_exposure_crc: Decimal
    current_credit_rwa_crc: Decimal
    portfolio_valuation_source: str
    capital_classification_sources: tuple[str, ...]


class PortfolioScenarioEvidenceBridge:
    """Join verified regulatory exposure to market-value sensitivities by lot.

    Regulatory exposure (SUGEF base) and market value are distinct amounts.
    The *proposed* APR assumes unchanged exposure/RWA per unit of CRC market
    value; this is an indicative rebalance, NOT a new regulatory assessment.
    Actual trades require revised exposures, cash/settlement and FX evidence.
    """

    @staticmethod
    def compare(
        capital_positions: Sequence[VerifiedCapitalPosition],
        market_risks: Sequence[VerifiedPositionMarketRisk],
        proposed_weights_by_position: Mapping[str, Decimal],
        *,
        cutoff: date,
        portfolio_market_value_crc: Decimal,
        portfolio_valuation_source: str,
        policy: ScenarioRiskPolicy,
    ) -> AuditedPortfolioScenario:
        def finite(value: Decimal) -> bool:
            return isinstance(value, Decimal) and value.is_finite()

        if (
            not finite(portfolio_market_value_crc)
            or portfolio_market_value_crc <= 0
            or not portfolio_valuation_source.strip()
        ):
            raise ValueError("Positive portfolio market value and audit source are required")

        positions = PortfolioCapitalEvidenceService.validate(capital_positions, cutoff=cutoff)
        risks = tuple(market_risks)
        risk_keys = tuple(row.position_key for row in risks)
        position_keys = tuple(row.position_key for row in positions)
        if (
            len(risk_keys) != len(set(risk_keys))
            or any(not key.strip() for key in risk_keys)
            or set(risk_keys) != set(position_keys)
        ):
            raise ValueError("Market-risk records must match every audited position exactly")
        if set(proposed_weights_by_position) != set(position_keys):
            raise ValueError("Proposed scenario must identify every position exactly")
        risk_by_key = {row.position_key: row for row in risks}

        for risk in risks:
            if risk.cutoff != cutoff or not all(
                source.strip()
                for source in (
                    risk.market_value_source,
                    risk.duration_source,
                    risk.dv01_source,
                    risk.hqla_source,
                )
            ):
                raise ValueError("Market-risk cutoff and all source references must be audited")
            if not all(
                finite(value)
                for value in (
                    risk.market_value_crc,
                    risk.modified_duration_years,
                    risk.dv01_crc,
                    risk.eligible_hqla_value_crc,
                )
            ):
                raise ValueError("Market-risk values must be finite Decimals")
            if (
                risk.market_value_crc <= 0
                or risk.modified_duration_years < 0
                or not 0 <= risk.eligible_hqla_value_crc <= risk.market_value_crc
            ):
                raise ValueError("Invalid market value, duration or eligible HQLA amount")

        ordered_risks = tuple(risk_by_key[key] for key in position_keys)
        summed_market = sum((row.market_value_crc for row in ordered_risks), Decimal("0"))
        if abs(summed_market - portfolio_market_value_crc) > Decimal("0.01"):
            raise ValueError("Portfolio market value does not reconcile to dated positions")

        exposures = tuple(
            CapitalExposure(
                security_key=row.position_key,
                issuer=row.issuer,
                currency=row.currency.strip().upper(),
                regulatory_exposure_crc=row.regulatory_exposure_crc,
                exposure_class=row.exposure_class,
                classification_source=row.classification_source,
            )
            for row in positions
        )
        evaluated_capital = PortfolioCapitalConsumptionService.evaluate(exposures)
        current_weights = tuple(
            risk.market_value_crc / summed_market for risk in ordered_risks
        )
        proposed_weights = tuple(
            proposed_weights_by_position[key] for key in position_keys
        )
        factors = tuple(
            VerifiedScenarioRiskAsset(
                security_key=risk.position_key,
                cutoff=cutoff,
                modified_duration_years=risk.modified_duration_years,
                dv01_crc_per_invested_crc=risk.dv01_crc / risk.market_value_crc,
                hqla_eligible_fraction=risk.eligible_hqla_value_crc / risk.market_value_crc,
                credit_rwa_crc_per_invested_crc=capital.credit_rwa_crc / risk.market_value_crc,
                duration_source=risk.duration_source,
                dv01_source=risk.dv01_source,
                hqla_source=risk.hqla_source,
                capital_source=position.regulatory_exposure_source,
            )
            for position, risk, capital in zip(
                positions, ordered_risks, evaluated_capital.items, strict=True
            )
        )
        comparison = PortfolioScenarioRiskService.compare(
            factors,
            current_weights,
            proposed_weights,
            cutoff=cutoff,
            portfolio_value_crc=summed_market,
            policy=policy,
        )
        return AuditedPortfolioScenario(
            comparison=comparison,
            position_keys=position_keys,
            current_weights=current_weights,
            proposed_weights=proposed_weights,
            regulatory_exposure_crc=evaluated_capital.total_regulatory_exposure_crc,
            current_credit_rwa_crc=evaluated_capital.total_credit_rwa_crc,
            portfolio_valuation_source=portfolio_valuation_source,
            capital_classification_sources=tuple(
                sorted({row.classification_source for row in positions})
            ),
        )
