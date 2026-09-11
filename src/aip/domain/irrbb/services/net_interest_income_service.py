from __future__ import annotations

from decimal import Decimal

from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.nii import (
    ConvertedNIIAccrual,
    NetInterestIncomeResult,
    NIIAccrualType,
    NIIInterestAccrual,
    NIIProjectionBasis,
)
from aip.domain.irrbb.ports import NIIExchangeRateProvider
from aip.shared.money import Currency, Money


class NetInterestIncomeService:
    """Aggregate explicit projected interest accruals into scenario NII.

    The service performs no repricing, renewal, balance-sheet replacement, curve
    construction or day-count inference. Those concerns must be resolved before an
    accrual crosses this boundary.
    """

    @classmethod
    def calculate(
        cls,
        *,
        accruals: tuple[NIIInterestAccrual, ...],
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
        reporting_currency: Currency,
        exchange_rates: NIIExchangeRateProvider | None = None,
    ) -> NetInterestIncomeResult:
        if not accruals:
            raise ValueError("NII calculation requires at least one accrual")

        interest_income = Decimal("0")
        interest_expense = Decimal("0")
        converted: list[ConvertedNIIAccrual] = []
        seen_ids: set[str] = set()

        for accrual in accruals:
            if accrual.accrual_id in seen_ids:
                raise ValueError(f"duplicate NII accrual_id: {accrual.accrual_id}")
            seen_ids.add(accrual.accrual_id)

            if accrual.scenario is not scenario:
                raise ValueError(
                    f"NII accrual {accrual.accrual_id} scenario does not match calculation scenario"
                )
            if accrual.accrual_start_date < basis.valuation_date:
                raise ValueError(f"NII accrual {accrual.accrual_id} starts before valuation_date")
            if accrual.accrual_end_date > basis.horizon_end_date:
                raise ValueError(
                    f"NII accrual {accrual.accrual_id} ends after the projection horizon"
                )

            fx = cls._exchange_rate(
                accrual=accrual,
                basis=basis,
                reporting_currency=reporting_currency,
                provider=exchange_rates,
            )
            amount_reporting = accrual.amount.amount * fx

            if accrual.accrual_type is NIIAccrualType.INTEREST_INCOME:
                interest_income += amount_reporting
                signed_contribution = amount_reporting
            else:
                interest_expense += amount_reporting
                signed_contribution = -amount_reporting

            converted.append(
                ConvertedNIIAccrual(
                    accrual=accrual,
                    exchange_rate=fx,
                    amount_reporting=Money(amount_reporting, reporting_currency),
                    signed_nii_contribution=Money(
                        signed_contribution,
                        reporting_currency,
                    ),
                )
            )

        net_interest_income = interest_income - interest_expense
        return NetInterestIncomeResult(
            basis=basis,
            scenario=scenario,
            reporting_currency=reporting_currency,
            interest_income=Money(interest_income, reporting_currency),
            interest_expense=Money(interest_expense, reporting_currency),
            net_interest_income=Money(net_interest_income, reporting_currency),
            accruals=tuple(converted),
        )

    @staticmethod
    def _exchange_rate(
        *,
        accrual: NIIInterestAccrual,
        basis: NIIProjectionBasis,
        reporting_currency: Currency,
        provider: NIIExchangeRateProvider | None,
    ) -> Decimal:
        if accrual.amount.currency is reporting_currency:
            return Decimal("1")
        if provider is None:
            raise ValueError(
                "NII exchange-rate provider required for "
                f"{accrual.amount.currency}->{reporting_currency}"
            )

        rate = provider.rate(
            from_currency=accrual.amount.currency,
            to_currency=reporting_currency,
            scenario=accrual.scenario,
            valuation_date=basis.valuation_date,
            accrual_end_date=accrual.accrual_end_date,
        )
        if not rate.is_finite() or rate <= 0:
            raise ValueError("NII exchange rate must be finite and positive")
        return rate
