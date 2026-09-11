from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from aip.domain.portfolio.services.portfolio_duration_service import (
    PortfolioDurationService,
)

FlowType = Literal["COUPON", "PRINCIPAL"]
AmountStatus = Literal["CONTRACTUAL", "PROJECTED_CURRENT_RATE"]


@dataclass(frozen=True, slots=True)
class PortfolioContractualCashFlow:
    payment_date: date
    flow_type: FlowType
    amount_local: Decimal
    currency: str
    amount_status: AmountStatus
    source: str


class PortfolioContractualCashFlowService:
    """Build contractual investment cash flows from normalized portfolio positions.

    Principal is based on outstanding nominal/principal rather than market value.
    Fixed-rate coupons are contractual. Variable-rate coupon amounts beyond the
    current reset are projected at the current nominal rate and explicitly
    labelled as such; payment dates remain contractual. Source positions are
    read-only inputs and are never mutated by this service.
    """

    @classmethod
    def calculate(
        cls,
        position: dict[str, Any],
        valuation_date: date,
    ) -> tuple[PortfolioContractualCashFlow, ...]:
        maturity = cls._as_date(position.get("maturity_date"))
        nominal = cls._decimal(position.get("nominal"))
        if nominal is None or nominal <= 0 or maturity is None or maturity <= valuation_date:
            return ()

        currency = str(position.get("currency") or "CRC").strip().upper()
        months = PortfolioDurationService._period_months(position.get("periodicity"))
        coupon_rate = cls._decimal(position.get("nominal_rate"))
        is_variable = PortfolioDurationService._is_variable(position)

        flows: list[PortfolioContractualCashFlow] = []

        if months is not None and coupon_rate is not None and coupon_rate > 0:
            coupon_amount = nominal * cls._rate_decimal(coupon_rate) * Decimal(months) / Decimal(12)
            payment_dates = cls._payment_dates(
                valuation_date=valuation_date,
                maturity=maturity,
                months=months,
                last_payment=cls._as_date(position.get("last_interest_payment_date")),
            )
            amount_status: AmountStatus = "PROJECTED_CURRENT_RATE" if is_variable else "CONTRACTUAL"
            source = (
                "CURRENT_RATE_PROJECTION_VARIABLE_SECURITY"
                if is_variable
                else "MASTER_FIXED_RATE_CONTRACT"
            )
            flows.extend(
                PortfolioContractualCashFlow(
                    payment_date=payment_date,
                    flow_type="COUPON",
                    amount_local=coupon_amount,
                    currency=currency,
                    amount_status=amount_status,
                    source=source,
                )
                for payment_date in payment_dates
            )

        flows.append(
            PortfolioContractualCashFlow(
                payment_date=maturity,
                flow_type="PRINCIPAL",
                amount_local=nominal,
                currency=currency,
                amount_status="CONTRACTUAL",
                source="MASTER_OUTSTANDING_NOMINAL",
            )
        )
        flows.sort(key=lambda item: (item.payment_date, item.flow_type))
        return tuple(flows)

    @classmethod
    def _payment_dates(
        cls,
        *,
        valuation_date: date,
        maturity: date,
        months: int,
        last_payment: date | None,
    ) -> tuple[date, ...]:
        first_payment = PortfolioDurationService._next_coupon_date(
            valuation_date=valuation_date,
            months=months,
            last_payment=last_payment,
            maturity=maturity,
        )
        if first_payment is None or first_payment <= valuation_date:
            return ()

        dates: list[date] = []
        current = first_payment
        while current <= maturity:
            dates.append(current)
            if current == maturity:
                break
            next_date = PortfolioDurationService._advance_months(current, months)
            current = maturity if next_date > maturity else next_date
        return tuple(dates)

    @staticmethod
    def _rate_decimal(value: Decimal) -> Decimal:
        return value / Decimal("100") if abs(value) > Decimal("1") else value

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError):
            return None

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None
