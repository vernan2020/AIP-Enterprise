from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRResult,
    ConfiguredPortfolioVaRService,
)


class PortfolioSimulationAction(StrEnum):
    """Supported hypothetical portfolio transaction types."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class PortfolioSimulationSecurity:
    """Security available to the price-risk simulator."""

    security_key: str
    fallback_key: str
    isin: str
    series: str
    issuer: str
    currency: str
    product_code: str
    maturity_date: date | None
    current_market_value_crc: Decimal
    market_price: Decimal | None
    market_yield: Decimal | None
    source: str
    in_portfolio: bool


@dataclass(frozen=True, slots=True)
class PortfolioSimulationTrade:
    """One hypothetical trade expressed as CRC-equivalent market value."""

    action: PortfolioSimulationAction
    security_key: str
    market_value_crc: Decimal

    def __post_init__(self) -> None:
        if not self.security_key.strip():
            raise ValueError("security_key is required")
        if self.market_value_crc <= 0:
            raise ValueError("market_value_crc must be greater than zero")


@dataclass(frozen=True, slots=True)
class AppliedPortfolioSimulationTrade:
    """Auditable trade after security resolution and validation."""

    action: PortfolioSimulationAction
    security_key: str
    series: str
    issuer: str
    currency: str
    market_value_crc: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioVaRSimulationResult:
    """Base-versus-hypothetical VeR comparison for one scenario."""

    valuation_date: date
    base_result: ConfiguredPortfolioVaRResult
    simulated_result: ConfiguredPortfolioVaRResult
    trades: tuple[AppliedPortfolioSimulationTrade, ...]

    base_var_crc: Decimal | None
    simulated_var_crc: Decimal | None
    delta_var_crc: Decimal | None
    base_var_percent: Decimal | None
    simulated_var_percent: Decimal | None
    delta_var_percent_points: Decimal | None
    relative_var_change_percent: Decimal | None

    base_market_value_crc: Decimal
    simulated_market_value_crc: Decimal
    delta_market_value_crc: Decimal
    base_scenario_number: int | None
    simulated_scenario_number: int | None

    status: str
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class ConfiguredPortfolioVaRSimulationService:
    """What-if engine for purchases, sales and mixed portfolio changes.

    The injected VeR service MUST be a dedicated simulation instance, separate
    from the canonical ``ConfiguredPortfolioVaRService`` registered for the
    production dashboard. This service therefore may force-refresh the same
    valuation date without contaminating the official base VeR cache.

    Every transaction amount is entered as CRC-equivalent market value, the
    same exposure basis consumed by the consolidated historical VeR engine.
    The institutional methodology itself is not reimplemented here: both the
    base and hypothetical portfolios are recalculated by the existing 521-price,
    21-observation, 500-scenario VeR service.
    """

    _SIMULATED_CLASSIFICATION = "SIMULATED_MARKET_VALUE"

    def __init__(
        self,
        portfolio_provider: ConfiguredPortfolioProvider,
        simulation_var_service: ConfiguredPortfolioVaRService,
    ) -> None:
        self._portfolio_provider = portfolio_provider
        self._simulation_var_service = simulation_var_service

    def list_securities(
        self,
        *,
        portfolio: dict[str, Any] | None = None,
    ) -> tuple[PortfolioSimulationSecurity, ...]:
        """Return current holdings plus the current PiPCA market universe."""

        source_portfolio = portfolio or self._portfolio_provider.get_portfolio()
        positions = self._positions(source_portfolio)
        by_key: dict[str, PortfolioSimulationSecurity] = {}
        by_fallback: dict[str, str] = {}

        for position in positions:
            security = self._security_from_position(position)
            if security is None:
                continue
            matched_key = by_fallback.get(security.fallback_key)
            if matched_key is None:
                by_key[security.security_key] = security
                by_fallback[security.fallback_key] = security.security_key
                continue
            existing = by_key[matched_key]
            by_key[matched_key] = PortfolioSimulationSecurity(
                security_key=existing.security_key,
                fallback_key=existing.fallback_key,
                isin=existing.isin or security.isin,
                series=existing.series or security.series,
                issuer=existing.issuer or security.issuer,
                currency=existing.currency or security.currency,
                product_code=existing.product_code or security.product_code,
                maturity_date=existing.maturity_date or security.maturity_date,
                current_market_value_crc=(
                    existing.current_market_value_crc + security.current_market_value_crc
                ),
                market_price=existing.market_price or security.market_price,
                market_yield=existing.market_yield or security.market_yield,
                source="PORTFOLIO",
                in_portfolio=True,
            )

        vector_payload = source_portfolio.get("price_vector") or {}
        vector_records = (
            vector_payload.get("records", ()) if isinstance(vector_payload, dict) else ()
        )
        for record in vector_records or ():
            if not isinstance(record, dict):
                continue
            candidate = self._security_from_vector(record)
            if candidate is None:
                continue
            if candidate.security_key in by_key:
                existing = by_key[candidate.security_key]
                by_key[candidate.security_key] = self._with_market_fields(existing, candidate)
                continue
            matched_key = by_fallback.get(candidate.fallback_key)
            if matched_key is not None:
                existing = by_key[matched_key]
                by_key[matched_key] = self._with_market_fields(existing, candidate)
                continue
            by_key[candidate.security_key] = candidate
            by_fallback[candidate.fallback_key] = candidate.security_key

        return tuple(
            sorted(
                by_key.values(),
                key=lambda item: (
                    not item.in_portfolio,
                    -item.current_market_value_crc,
                    item.issuer.casefold(),
                    item.series.casefold(),
                ),
            )
        )

    def simulate(
        self,
        trades: tuple[PortfolioSimulationTrade, ...],
        *,
        portfolio: dict[str, Any] | None = None,
    ) -> ConfiguredPortfolioVaRSimulationResult:
        """Apply hypothetical transactions and recalculate VeR without persistence."""

        if not trades:
            raise ValueError("At least one simulation trade is required")

        source_portfolio = portfolio or self._portfolio_provider.get_portfolio()
        valuation_date = self._valuation_date(source_portfolio)
        universe = self.list_securities(portfolio=source_portfolio)
        universe_by_key = {item.security_key: item for item in universe}

        hypothetical = deepcopy(source_portfolio)
        hypothetical_positions = self._positions(hypothetical)
        applied: list[AppliedPortfolioSimulationTrade] = []

        for trade in trades:
            security = universe_by_key.get(trade.security_key)
            if security is None:
                raise ValueError(
                    f"Security {trade.security_key!r} is not available in the simulation universe"
                )
            if trade.action is PortfolioSimulationAction.BUY:
                self._apply_buy(hypothetical_positions, security, trade.market_value_crc)
            elif trade.action is PortfolioSimulationAction.SELL:
                self._apply_sell(hypothetical_positions, security, trade.market_value_crc)
            else:  # pragma: no cover
                raise ValueError(f"Unsupported simulation action: {trade.action}")
            applied.append(
                AppliedPortfolioSimulationTrade(
                    action=trade.action,
                    security_key=security.security_key,
                    series=security.series,
                    issuer=security.issuer,
                    currency=security.currency,
                    market_value_crc=trade.market_value_crc,
                    source=security.source,
                )
            )

        hypothetical["positions"] = [
            position
            for position in hypothetical_positions
            if self._market_value(position) > Decimal("0")
        ]

        # This service owns a simulation-only VeR calculator, so forced refreshes
        # cannot overwrite the official cache used by the production dashboard.
        base_result = self._simulation_var_service.calculate(
            valuation_date=valuation_date,
            portfolio=source_portfolio,
            force_refresh=True,
        )
        simulated_result = self._simulation_var_service.calculate(
            valuation_date=valuation_date,
            portfolio=hypothetical,
            force_refresh=True,
        )

        base_var_crc, base_var_percent, base_scenario = self._var_values(base_result)
        simulated_var_crc, simulated_var_percent, simulated_scenario = self._var_values(
            simulated_result
        )
        delta_var_crc = self._difference(simulated_var_crc, base_var_crc)
        delta_var_percent_points = self._difference(simulated_var_percent, base_var_percent)

        relative_var_change_percent = None
        if (
            base_var_crc is not None
            and simulated_var_crc is not None
            and base_var_crc != Decimal("0")
        ):
            relative_var_change_percent = (
                (simulated_var_crc - base_var_crc) / base_var_crc * Decimal("100")
            )

        warnings = self._warnings(
            base_result=base_result,
            simulated_result=simulated_result,
        )
        notes = self._notes(tuple(applied))
        if base_var_crc is None or simulated_var_crc is None:
            status = "UNAVAILABLE"
        elif warnings:
            status = "CALCULATED_WITH_WARNINGS"
        else:
            status = "CALCULATED"

        base_market_value = base_result.calculated_market_value_crc
        simulated_market_value = simulated_result.calculated_market_value_crc

        return ConfiguredPortfolioVaRSimulationResult(
            valuation_date=valuation_date,
            base_result=base_result,
            simulated_result=simulated_result,
            trades=tuple(applied),
            base_var_crc=base_var_crc,
            simulated_var_crc=simulated_var_crc,
            delta_var_crc=delta_var_crc,
            base_var_percent=base_var_percent,
            simulated_var_percent=simulated_var_percent,
            delta_var_percent_points=delta_var_percent_points,
            relative_var_change_percent=relative_var_change_percent,
            base_market_value_crc=base_market_value,
            simulated_market_value_crc=simulated_market_value,
            delta_market_value_crc=simulated_market_value - base_market_value,
            base_scenario_number=base_scenario,
            simulated_scenario_number=simulated_scenario,
            status=status,
            warnings=warnings,
            notes=notes,
        )

    def _apply_buy(
        self,
        positions: list[dict[str, Any]],
        security: PortfolioSimulationSecurity,
        amount: Decimal,
    ) -> None:
        matches = self._matching_positions(positions, security)
        if matches:
            self._set_market_value(matches[0], self._market_value(matches[0]) + amount)
            return
        positions.append(
            {
                "isin": security.isin,
                "issuer": security.issuer,
                "series": security.series,
                "product_code": security.product_code,
                "instrument": security.product_code or security.series,
                "currency": security.currency,
                "market_value_crc": float(amount),
                "market_value": float(amount),
                "market_value_local": float(amount),
                "classification": self._SIMULATED_CLASSIFICATION,
                "maturity_date": security.maturity_date,
                "market_price": (
                    float(security.market_price) if security.market_price is not None else None
                ),
                "market_yield": (
                    float(security.market_yield) if security.market_yield is not None else None
                ),
                "source_values": {},
                "simulation_origin": "PIPCA_MARKET_UNIVERSE",
            }
        )

    def _apply_sell(
        self,
        positions: list[dict[str, Any]],
        security: PortfolioSimulationSecurity,
        amount: Decimal,
    ) -> None:
        matches = self._matching_positions(positions, security)
        current = sum((self._market_value(item) for item in matches), Decimal("0"))
        if not matches or current <= Decimal("0"):
            raise ValueError(f"Security {security.series} is not currently held in the portfolio")
        if amount > current:
            raise ValueError(
                f"Sale of {amount} exceeds current CRC-equivalent market value {current} "
                f"for {security.series}"
            )

        remaining = amount
        for position in matches:
            if remaining <= 0:
                break
            current_value = self._market_value(position)
            reduction = min(current_value, remaining)
            self._set_market_value(position, current_value - reduction)
            remaining -= reduction

    def _matching_positions(
        self,
        positions: list[dict[str, Any]],
        security: PortfolioSimulationSecurity,
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for position in positions:
            identity = self._identity_from_position(position)
            if identity is None:
                continue
            security_key, fallback_key = identity
            if security_key == security.security_key or fallback_key == security.fallback_key:
                matches.append(position)
        return matches

    def _security_from_position(
        self,
        position: dict[str, Any],
    ) -> PortfolioSimulationSecurity | None:
        identity = self._identity_from_position(position)
        if identity is None:
            return None
        security_key, fallback_key = identity
        series = str(
            position.get("series") or position.get("series_or_security_code") or ""
        ).strip()
        issuer = str(position.get("issuer") or "").strip()
        isin = str(position.get("isin") or position.get("isin_if_present") or "").strip()
        product_code = str(position.get("product_code") or "").strip()
        currency = str(
            position.get("currency") or self._infer_currency(product_code, series)
        ).upper()
        maturity = self._as_date(
            position.get("maturity_date") or position.get("maturity_date_if_present")
        )
        return PortfolioSimulationSecurity(
            security_key=security_key,
            fallback_key=fallback_key,
            isin=isin,
            series=series,
            issuer=issuer,
            currency=currency,
            product_code=product_code,
            maturity_date=maturity,
            current_market_value_crc=self._market_value(position),
            market_price=self._optional_decimal(position.get("market_price")),
            market_yield=self._optional_decimal(position.get("market_yield")),
            source="PORTFOLIO",
            in_portfolio=True,
        )

    def _security_from_vector(
        self,
        record: dict[str, Any],
    ) -> PortfolioSimulationSecurity | None:
        series = str(record.get("series_or_security_code") or record.get("series") or "").strip()
        issuer = str(record.get("issuer") or "").strip()
        if not series or not issuer:
            return None
        market_price = self._optional_decimal(record.get("market_price"))
        if market_price is None or market_price <= 0:
            return None
        isin = str(record.get("isin_if_present") or record.get("isin") or "").strip()
        product_code = str(record.get("instrument_type_or_mnemonic") or "").strip()
        maturity = self._as_date(
            record.get("maturity_date_if_present") or record.get("maturity_date")
        )
        security_key = self._security_key(
            isin=isin,
            series=series,
            issuer=issuer,
            maturity_date=maturity,
        )
        fallback_key = self._fallback_key(
            series=series,
            issuer=issuer,
            maturity_date=maturity,
        )
        return PortfolioSimulationSecurity(
            security_key=security_key,
            fallback_key=fallback_key,
            isin=isin,
            series=series,
            issuer=issuer,
            currency=self._infer_currency(product_code, series),
            product_code=product_code,
            maturity_date=maturity,
            current_market_value_crc=Decimal("0"),
            market_price=market_price,
            market_yield=self._optional_decimal(record.get("market_yield")),
            source="PIPCA",
            in_portfolio=False,
        )

    @staticmethod
    def _with_market_fields(
        existing: PortfolioSimulationSecurity,
        market: PortfolioSimulationSecurity,
    ) -> PortfolioSimulationSecurity:
        return PortfolioSimulationSecurity(
            security_key=existing.security_key,
            fallback_key=existing.fallback_key,
            isin=existing.isin or market.isin,
            series=existing.series or market.series,
            issuer=existing.issuer or market.issuer,
            currency=existing.currency or market.currency,
            product_code=existing.product_code or market.product_code,
            maturity_date=existing.maturity_date or market.maturity_date,
            current_market_value_crc=existing.current_market_value_crc,
            market_price=market.market_price or existing.market_price,
            market_yield=market.market_yield or existing.market_yield,
            source="PORTFOLIO" if existing.in_portfolio else market.source,
            in_portfolio=existing.in_portfolio,
        )

    def _identity_from_position(
        self,
        position: dict[str, Any],
    ) -> tuple[str, str] | None:
        series = str(
            position.get("series") or position.get("series_or_security_code") or ""
        ).strip()
        issuer = str(position.get("issuer") or "").strip()
        isin = str(position.get("isin") or position.get("isin_if_present") or "").strip()
        maturity = self._as_date(
            position.get("maturity_date") or position.get("maturity_date_if_present")
        )
        if not isin and not series:
            return None
        return (
            self._security_key(
                isin=isin,
                series=series,
                issuer=issuer,
                maturity_date=maturity,
            ),
            self._fallback_key(
                series=series,
                issuer=issuer,
                maturity_date=maturity,
            ),
        )

    @staticmethod
    def _security_key(
        *,
        isin: str,
        series: str,
        issuer: str,
        maturity_date: date | None,
    ) -> str:
        normalized_isin = isin.strip().casefold()
        if normalized_isin:
            return f"isin:{normalized_isin}"
        return ConfiguredPortfolioVaRSimulationService._fallback_key(
            series=series,
            issuer=issuer,
            maturity_date=maturity_date,
        )

    @staticmethod
    def _fallback_key(
        *,
        series: str,
        issuer: str,
        maturity_date: date | None,
    ) -> str:
        maturity_text = maturity_date.isoformat() if maturity_date is not None else ""
        return (
            f"series:{series.strip().casefold()}"
            f"|issuer:{issuer.strip().casefold()}"
            f"|maturity:{maturity_text}"
        )

    @staticmethod
    def _infer_currency(product_code: str, series: str) -> str:
        text = f"{product_code} {series}".upper()
        return "USD" if "$" in text or "USD" in text else "CRC"

    @staticmethod
    def _positions(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
        raw = portfolio.get("positions") or []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    @classmethod
    def _market_value(cls, position: dict[str, Any]) -> Decimal:
        if "market_value_crc" in position and position.get("market_value_crc") not in (None, ""):
            return cls._decimal(position.get("market_value_crc"))
        return cls._decimal(position.get("market_value"))

    @staticmethod
    def _set_market_value(position: dict[str, Any], value: Decimal) -> None:
        numeric = float(value)
        position["market_value_crc"] = numeric
        position["market_value"] = numeric
        position["market_value_local"] = numeric

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value in (None, ""):
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _optional_decimal(value: object) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _as_date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    @classmethod
    def _valuation_date(cls, portfolio: dict[str, Any]) -> date:
        resolved = cls._as_date(portfolio.get("valuation_date"))
        if resolved is None:
            raise ValueError("Portfolio valuation date is unavailable for simulation")
        return resolved

    @staticmethod
    def _difference(left: Decimal | None, right: Decimal | None) -> Decimal | None:
        if left is None or right is None:
            return None
        return left - right

    @staticmethod
    def _var_values(
        result: ConfiguredPortfolioVaRResult,
    ) -> tuple[Decimal | None, Decimal | None, int | None]:
        if result.portfolio_var is None:
            return None, None, None
        return (
            result.portfolio_var.portfolio_var_crc,
            result.portfolio_var.portfolio_var_percent,
            result.portfolio_var.var_scenario_number,
        )

    @staticmethod
    def _warnings(
        *,
        base_result: ConfiguredPortfolioVaRResult,
        simulated_result: ConfiguredPortfolioVaRResult,
    ) -> tuple[str, ...]:
        warnings: list[str] = []
        if simulated_result.excluded_title_count > base_result.excluded_title_count:
            difference = simulated_result.excluded_title_count - base_result.excluded_title_count
            warnings.append(
                f"{difference} título(s) adicional(es) del escenario no pudieron incorporarse "
                "al VeR por ausencia o error de historia."
            )
        if (
            simulated_result.policy_excluded_position_count
            > base_result.policy_excluded_position_count
        ):
            difference = (
                simulated_result.policy_excluded_position_count
                - base_result.policy_excluded_position_count
            )
            warnings.append(
                f"{difference} posición(es) adicional(es) quedaron fuera del universo VeR "
                "por política metodológica."
            )
        if simulated_result.coverage_percent + Decimal("0.01") < base_result.coverage_percent:
            warnings.append(
                "La cobertura histórica bajó de "
                f"{base_result.coverage_percent:.2f}% a "
                f"{simulated_result.coverage_percent:.2f}%."
            )
        return tuple(warnings)

    @staticmethod
    def _notes(
        applied_trades: tuple[AppliedPortfolioSimulationTrade, ...],
    ) -> tuple[str, ...]:
        notes: list[str] = []
        if any(
            item.action is PortfolioSimulationAction.BUY and item.source == "PIPCA"
            for item in applied_trades
        ):
            notes.append(
                "Las compras de títulos fuera del portafolio usan su historia PiPCA y el monto "
                "de exposición CRC ingresado; no se modifica el portafolio real."
            )
        return tuple(notes)
