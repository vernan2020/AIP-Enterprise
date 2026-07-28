from enum import Enum


class PaymentFrequency(Enum):
    """Payment frequency values."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"

    @classmethod
    def from_value(cls, value: "PaymentFrequency | str | None") -> "PaymentFrequency":
        if value is None:
            raise ValueError("Payment frequency must be provided")
        if isinstance(value, Enum):
            for member in cls:
                if value.name == member.name:
                    return member
        if isinstance(value, str):
            normalized_value = value.strip().lower()
            for member in cls:
                if normalized_value == member.value or normalized_value == member.name.lower():
                    return member
        raise ValueError(f"Unsupported payment frequency: {value!r}")

    def months_between_payments(self) -> int:
        mapping = {
            PaymentFrequency.MONTHLY: 1,
            PaymentFrequency.QUARTERLY: 3,
            PaymentFrequency.SEMIANNUAL: 6,
            PaymentFrequency.ANNUAL: 12,
        }
        return mapping[self]
