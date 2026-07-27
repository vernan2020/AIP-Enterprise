"""ISIN value object with structural and checksum validation."""

import re
from dataclasses import dataclass

from src.aip.domain.portfolio.exceptions import InvalidPositionError


_ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


@dataclass(frozen=True, slots=True)
class ISIN:
    """Represents a valid 12-character ISIN code."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        object.__setattr__(self, "value", normalized)

        if not _ISIN_PATTERN.match(normalized):
            raise InvalidPositionError("ISIN must match ISO 6166 12-character structure.")

        if not self._is_valid_checksum(normalized):
            raise InvalidPositionError("ISIN checksum validation failed.")

    @staticmethod
    def _is_valid_checksum(isin: str) -> bool:
        expanded = ""
        for char in isin:
            if char.isdigit():
                expanded += char
            else:
                expanded += str(ord(char) - 55)

        total = 0
        reverse_digits = expanded[::-1]
        for index, raw_digit in enumerate(reverse_digits):
            digit = int(raw_digit)
            if index % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit = digit // 10 + digit % 10
            total += digit

        return total % 10 == 0

    def __str__(self) -> str:
        """Return normalized ISIN."""
        return self.value
