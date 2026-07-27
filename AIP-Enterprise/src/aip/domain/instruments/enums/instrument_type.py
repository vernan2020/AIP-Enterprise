from enum import Enum


class InstrumentType(Enum):
    """Supported instrument categories."""

    GOVERNMENT_BOND = "government_bond"
    TREASURY_BILL = "treasury_bill"
    ZERO_COUPON_BOND = "zero_coupon_bond"
    FLOATING_RATE_BOND = "floating_rate_bond"
    CASH = "cash"
    INVESTMENT_FUND = "investment_fund"
    CERTIFICATE_OF_DEPOSIT = "certificate_of_deposit"
    COMMERCIAL_PAPER = "commercial_paper"
    REPO = "repo"
    REVERSE_REPO = "reverse_repo"
