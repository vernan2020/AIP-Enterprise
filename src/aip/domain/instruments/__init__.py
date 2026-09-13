"""Instrument domain package for AIP Enterprise."""

import sys

from .base.financial_instrument import FinancialInstrument
from .bonds.bond import Bond
from .bonds.floating_rate_bond import FloatingRateBond
from .bonds.government_bond import GovernmentBond
from .bonds.treasury_bill import TreasuryBill
from .bonds.zero_coupon_bond import ZeroCouponBond
from .cash.cash import Cash
from .enums.amortization_type import AmortizationType
from .enums.coupon_type import CouponType
from .enums.instrument_type import InstrumentType
from .enums.payment_frequency import PaymentFrequency
from .funds.investment_fund import InvestmentFund
from .issuers.credit_rating import CreditRating
from .issuers.issuer import Issuer
from .issuers.issuer_type import IssuerType
from .money_market.certificate_of_deposit import CertificateOfDeposit
from .money_market.commercial_paper import CommercialPaper
from .money_market.repo import Repo
from .money_market.reverse_repo import ReverseRepo
from .schedules.coupon import Coupon
from .schedules.coupon_schedule import CouponSchedule
from .services.instrument_factory import InstrumentFactory

if "aip.domain.instruments.cash.cash" in sys.modules:
    cash_module = sys.modules["aip.domain.instruments.cash.cash"]
    sys.modules.setdefault("src.aip.domain.instruments.cash.cash", cash_module)
    sys.modules.setdefault("src.aip.domain.instruments.cash.cash.Cash", cash_module.Cash)

if "src.aip.domain.instruments.cash.cash" in sys.modules:
    cash_module = sys.modules["src.aip.domain.instruments.cash.cash"]
    sys.modules.setdefault("aip.domain.instruments.cash.cash", cash_module)
    sys.modules.setdefault("aip.domain.instruments.cash.cash.Cash", cash_module.Cash)

__all__ = [
    "FinancialInstrument",
    "Bond",
    "GovernmentBond",
    "TreasuryBill",
    "ZeroCouponBond",
    "FloatingRateBond",
    "Cash",
    "InvestmentFund",
    "Issuer",
    "IssuerType",
    "CreditRating",
    "Coupon",
    "CouponSchedule",
    "InstrumentFactory",
    "InstrumentType",
    "CouponType",
    "AmortizationType",
    "PaymentFrequency",
    "CertificateOfDeposit",
    "CommercialPaper",
    "Repo",
    "ReverseRepo",
]
