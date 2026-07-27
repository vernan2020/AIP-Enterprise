from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.instruments.bonds.floating_rate_bond import FloatingRateBond
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.bonds.treasury_bill import TreasuryBill
from aip.domain.instruments.bonds.zero_coupon_bond import ZeroCouponBond
from aip.domain.instruments.cash.cash import Cash
from aip.domain.instruments.money_market.certificate_of_deposit import CertificateOfDeposit
from aip.domain.instruments.money_market.commercial_paper import CommercialPaper
from aip.domain.instruments.money_market.repo import Repo
from aip.domain.instruments.money_market.reverse_repo import ReverseRepo
from aip.domain.pricing.calculators.bond_pricer import price_bond
from aip.domain.pricing.calculators.cash_pricer import price_cash
from aip.domain.pricing.calculators.floating_rate_pricer import price_floating_rate
from aip.domain.pricing.calculators.treasury_bill_pricer import price_treasury_bill
from aip.domain.pricing.calculators.zero_coupon_pricer import price_zero_coupon
from aip.domain.pricing.exceptions import PricingError


class PricingService:
    """Application service that selects the appropriate pricer for an instrument."""

    def price(self, instrument: object, *, valuation_date: date, market_yield: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        if isinstance(instrument, GovernmentBond):
            return price_bond(instrument, valuation_date=valuation_date, market_yield=market_yield)
        if isinstance(instrument, TreasuryBill):
            return price_treasury_bill(instrument, valuation_date=valuation_date, market_yield=market_yield)
        if isinstance(instrument, ZeroCouponBond):
            return price_zero_coupon(instrument, valuation_date=valuation_date, market_yield=market_yield)
        if isinstance(instrument, FloatingRateBond):
            return price_floating_rate(instrument, valuation_date=valuation_date, market_yield=market_yield)
        if isinstance(instrument, CertificateOfDeposit | CommercialPaper | Repo | ReverseRepo):
            return price_bond(instrument, valuation_date=valuation_date, market_yield=market_yield)
        if isinstance(instrument, Cash):
            return price_cash(instrument, valuation_date=valuation_date, market_yield=market_yield)
        raise PricingError("Unsupported instrument type")
