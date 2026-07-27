from enum import Enum


class PaymentFrequency(Enum):
    """Payment frequency values."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"

    def months_between_payments(self) -> int:
        mapping = {
            PaymentFrequency.MONTHLY: 1,
            PaymentFrequency.QUARTERLY: 3,
            PaymentFrequency.SEMIANNUAL: 6,
            PaymentFrequency.ANNUAL: 12,
        }
        return mapping[self]
