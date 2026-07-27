from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreditRating:
    """Represents a credit rating value object."""

    value: str
    agency: str
