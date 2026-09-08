from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.portfolio.services.portfolio_contractual_cashflow_service import (
    PortfolioContractualCashFlow,
    PortfolioContractualCashFlowService,
)
from aip.product.configured.adapters.configured_liquidity_provider import (
    ConfiguredLiquidityProvider,
)


class ConfiguredContractualLiquidityProvider(ConfiguredLiquidityProvider):
    """Liquidity provider enriched with contractual portfolio cash flows."""

    _HORIZONS = (30, 90, 180, 270)

    def _populate_portfolio_liquidity(
        self,
        *,
        result: dict[str, Any],
        positions: list[dict[str, Any]],
        valuation_date: date,
    ) -> None:
        super()._populate_portfolio_liquidity(
            result=result,
            positions=positions,
            valuation_date=valuation_date,
        )

        cashflow_rows: list[dict[str, Any]] = []
        maturity_rows: list[dict[str, Any]] = []
        coupon_totals = {horizon: Decimal("0") for horizon in self._HORIZONS}
        principal_totals = {horizon: Decimal("0") for horizon in self._HORIZONS}
        unresolved_conversion_count = 0

        for position in positions:
            conversion_factor, conversion_source = self._crc_conversion(position)
            flows = PortfolioContractualCashFlowService.calculate(position, valuation_date)
            for flow in flows:
                days = (flow.payment_date - valuation_date).days
                amount_crc = (
                    flow.amount_local * conversion_factor
                    if conversion_factor is not None
                    else None
                )
                if amount_crc is None:
                    unresolved_conversion_count += 1

                row = self._cashflow_row(
                    position=position,
                    flow=flow,
                    days=days,
                    amount_crc=amount_crc,
                    conversion_source=conversion_source,
                )
                cashflow_rows.append(row)

                if flow.flow_type == "PRINCIPAL":
                    maturity_rows.append(
                        {
                            **row,
                            "section": "MATURITY",
                            "value": float(amount_crc) if amount_crc is not None else 0.0,
                            "market_value_crc": self._float_value(position.get("market_value_crc")),
                            "status": "AVAILABLE" if amount_crc is not None else "FX_UNAVAILABLE",
                        }
                    )

                if amount_crc is None:
                    continue
                target = coupon_totals if flow.flow_type == "COUPON" else principal_totals
                for horizon in self._HORIZONS:
                    if days <= horizon:
                        target[horizon] += amount_crc

        cashflow_rows.sort(
            key=lambda row: (
                str(row.get("payment_date") or ""),
                str(row.get("flow_type") or ""),
                str(row.get("label") or ""),
            )
        )
        maturity_rows.sort(
            key=lambda row: (
                int(row.get("days_to_maturity") or 999999),
                str(row.get("label") or ""),
            )
        )

        payload: dict[str, Any] = {
            "cashflows": cashflow_rows,
            "maturity_rows": maturity_rows,
            "cashflow_conversion_unavailable_count": unresolved_conversion_count,
        }
        for horizon in self._HORIZONS:
            coupon = coupon_totals[horizon]
            principal = principal_totals[horizon]
            payload[f"coupon_inflows_{horizon}d_crc"] = float(coupon)
            payload[f"principal_inflows_{horizon}d_crc"] = float(principal)
            payload[f"investment_inflows_{horizon}d_crc"] = float(coupon + principal)
            payload[f"maturity_{horizon}d_crc"] = float(principal)

        result.update(payload)

    def _cashflow_row(
        self,
        *,
        position: dict[str, Any],
        flow: PortfolioContractualCashFlow,
        days: int,
        amount_crc: Decimal | None,
        conversion_source: str,
    ) -> dict[str, Any]:
        return {
            "section": "CASHFLOW",
            "label": str(position.get("series") or position.get("instrument") or ""),
            "issuer": str(position.get("issuer") or ""),
            "currency": flow.currency,
            "classification": str(position.get("classification") or ""),
            "payment_date": flow.payment_date.isoformat(),
            "maturity_date": flow.payment_date.isoformat(),
            "days_to_maturity": days,
            "bucket": self._maturity_bucket(days),
            "flow_type": flow.flow_type,
            "amount_local": float(flow.amount_local),
            "amount_crc": float(amount_crc) if amount_crc is not None else None,
            "value": float(amount_crc) if amount_crc is not None else float(flow.amount_local),
            "market_value_crc": self._float_value(position.get("market_value_crc")),
            "status": flow.amount_status if amount_crc is not None else "FX_UNAVAILABLE",
            "policy_reference": flow.source,
            "conversion_source": conversion_source,
        }

    @staticmethod
    def _crc_conversion(position: dict[str, Any]) -> tuple[Decimal | None, str]:
        currency = str(position.get("currency") or "CRC").strip().upper()
        if currency == "CRC":
            return Decimal("1"), "NATIVE_CRC"

        market_value_local = ConfiguredContractualLiquidityProvider._decimal(
            position.get("market_value_local") or position.get("market_value")
        )
        market_value_crc = ConfiguredContractualLiquidityProvider._decimal(
            position.get("market_value_crc")
        )
        if (
            market_value_local is None
            or market_value_crc is None
            or market_value_local <= 0
            or market_value_crc <= 0
        ):
            return None, "UNAVAILABLE"

        return market_value_crc / market_value_local, "MARKET_VALUE_IMPLIED_FX"

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError):
            return None
