"""SettlementDate value object."""

from dataclasses import dataclass

from src.aip.shared.dates import BusinessDate


@dataclass(frozen=True, slots=True)
class SettlementDate:
    """Represents settlement as a business-aware date value object."""

    value: BusinessDate

    @property
    def date(self):
        """Return settlement calendar date."""
        return self.value.date
