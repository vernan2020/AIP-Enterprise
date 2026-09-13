from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRService,
)
from aip.product.configured.services.configured_portfolio_var_simulation_service import (
    ConfiguredPortfolioVaRSimulationService,
    PortfolioSimulationSecurity,
)


class ConfiguredVectorPortfolioVaRSimulationService(ConfiguredPortfolioVaRSimulationService):
    """VeR what-if service with an exhaustive current-vector security catalog.

    The simulator accepts a CRC-equivalent market-value amount, so catalog
    membership must not depend on whether the current PiPCA row carries a
    usable price. Every vector row with a resolvable security series is exposed
    for BUY scenarios. Current holdings are merged into the same universe and
    retain the portfolio flag used by the UI to restrict SELL scenarios.

    This class deliberately leaves the institutional VeR calculation in the
    parent service untouched. It only strengthens the security-catalog boundary.
    """

    def __init__(
        self,
        portfolio_provider: ConfiguredPortfolioProvider,
        simulation_var_service: ConfiguredPortfolioVaRService,
    ) -> None:
        super().__init__(portfolio_provider, simulation_var_service)
        self._catalog_portfolio_provider = portfolio_provider

    def list_securities(
        self,
        *,
        portfolio: dict[str, Any] | None = None,
    ) -> tuple[PortfolioSimulationSecurity, ...]:
        """Return holdings plus every resolvable title in the current vector.

        Canonical and issuer-aware fallback keys deduplicate identical titles.
        Series+maturity is used only to reconcile vector rows against current
        holdings whose issuer label differs from PiPCA. It is intentionally not
        used to collapse vector-only rows from different issuers.
        """

        source_portfolio = (
            portfolio if portfolio is not None else self._catalog_portfolio_provider.get_portfolio()
        )
        by_key: dict[str, PortfolioSimulationSecurity] = {}
        by_fallback: dict[str, str] = {}
        by_series_maturity: dict[str, str] = {}

        for position in self._positions(source_portfolio):
            security = self._security_from_position(position)
            if security is None:
                continue
            matched_key = self._resolve_existing_key(
                security,
                by_key=by_key,
                by_fallback=by_fallback,
                by_series_maturity=by_series_maturity,
            )
            if matched_key is None:
                by_key[security.security_key] = security
                self._index_security(
                    security,
                    stored_key=security.security_key,
                    by_fallback=by_fallback,
                    by_series_maturity=by_series_maturity,
                )
                continue

            existing = by_key[matched_key]
            merged = PortfolioSimulationSecurity(
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
            by_key[matched_key] = merged
            self._index_security(
                merged,
                stored_key=matched_key,
                by_fallback=by_fallback,
                by_series_maturity=by_series_maturity,
            )

        for record in self._vector_records(source_portfolio):
            candidate = self._security_from_vector(record)
            if candidate is None:
                continue
            matched_key = self._resolve_existing_key(
                candidate,
                by_key=by_key,
                by_fallback=by_fallback,
                by_series_maturity=by_series_maturity,
            )
            if matched_key is None:
                by_key[candidate.security_key] = candidate
                self._index_security(
                    candidate,
                    stored_key=candidate.security_key,
                    by_fallback=by_fallback,
                    by_series_maturity=by_series_maturity,
                )
                continue

            merged = self._with_market_fields(by_key[matched_key], candidate)
            by_key[matched_key] = merged
            self._index_security(
                merged,
                stored_key=matched_key,
                by_fallback=by_fallback,
                by_series_maturity=by_series_maturity,
            )

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

    @staticmethod
    def _vector_records(portfolio: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        payload = portfolio.get("price_vector")
        if not isinstance(payload, dict):
            return ()
        raw_records = payload.get("records")
        if not isinstance(raw_records, (list, tuple)):
            raw_records = payload.get("positions")
        if not isinstance(raw_records, (list, tuple)):
            return ()
        return tuple(item for item in raw_records if isinstance(item, dict))

    def _security_from_vector(
        self,
        record: dict[str, Any],
    ) -> PortfolioSimulationSecurity | None:
        """Map a PiPCA row without dropping valid titles for missing quote fields."""

        series = str(
            record.get("series_or_security_code")
            or record.get("series")
            or record.get("security_code")
            or record.get("normalized_series_key")
            or ""
        ).strip()
        if not series:
            return None

        issuer = str(record.get("issuer") or record.get("normalized_issuer_key") or "N/D").strip()
        isin = str(record.get("isin_if_present") or record.get("isin") or "").strip()
        product_code = str(
            record.get("instrument_type_or_mnemonic") or record.get("mnemonic") or ""
        ).strip()
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
            market_price=self._optional_decimal(record.get("market_price")),
            market_yield=self._optional_decimal(record.get("market_yield")),
            source="PIPCA",
            in_portfolio=False,
        )

    @classmethod
    def _series_maturity_key(
        cls,
        security: PortfolioSimulationSecurity,
    ) -> str:
        maturity = (
            security.maturity_date.isoformat() if isinstance(security.maturity_date, date) else ""
        )
        return f"{security.series.strip().casefold()}|{maturity}"

    @classmethod
    def _resolve_existing_key(
        cls,
        security: PortfolioSimulationSecurity,
        *,
        by_key: dict[str, PortfolioSimulationSecurity],
        by_fallback: dict[str, str],
        by_series_maturity: dict[str, str],
    ) -> str | None:
        if security.security_key in by_key:
            return security.security_key
        fallback_match = by_fallback.get(security.fallback_key)
        if fallback_match is not None:
            return fallback_match
        return by_series_maturity.get(cls._series_maturity_key(security))

    @classmethod
    def _index_security(
        cls,
        security: PortfolioSimulationSecurity,
        *,
        stored_key: str,
        by_fallback: dict[str, str],
        by_series_maturity: dict[str, str],
    ) -> None:
        by_fallback[security.fallback_key] = stored_key
        if security.in_portfolio:
            by_series_maturity[cls._series_maturity_key(security)] = stored_key
