from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation

BORROWING_CUTOFF_RULE_REFERENCE = "aip://irrbb/source-rules/borrowings/month-end-sheet-cutoff/v1"
BORROWING_RESET_DAY_RULE_REFERENCE = "aip://irrbb/source-rules/borrowings/fecha-pago-reset-day/v1"
BORROWING_RESET_FREQUENCY_RULE_REFERENCE = (
    "aip://irrbb/source-rules/borrowings/actualizacion-reset-frequency/v1"
)


class BorrowingSourceRules:
    """Governed semantic derivations for the institutional borrowing workbook.

    The rules encode only institutionally confirmed semantics. They deliberately
    preserve fail-closed behavior when the source does not contain enough evidence
    to determine an exact contractual date.
    """

    _SHEET_PATTERN = re.compile(
        r"^(?P<month>ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SET|SEP|OCT|NOV|DIC)-(?P<year>\d{2})$"
    )
    _MONTH_BY_TOKEN = {
        "ENE": 1,
        "FEB": 2,
        "MAR": 3,
        "ABR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AGO": 8,
        "SET": 9,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DIC": 12,
    }
    _RESET_FREQUENCY_MONTHS = {
        "MENSUAL": 1,
        "TRIMESTRAL": 3,
    }

    @classmethod
    def month_end_cutoff(cls, sheet_name: str) -> date | None:
        """Derive the month-end cutoff from an exact governed worksheet label."""

        match = cls._SHEET_PATTERN.fullmatch(sheet_name.strip().upper())
        if match is None:
            return None
        month = cls._MONTH_BY_TOKEN[match.group("month")]
        year = 2000 + int(match.group("year"))
        return date(year, month, monthrange(year, month)[1])

    @classmethod
    def reset_frequency_months(cls, value: object) -> int | None:
        """Map the governed ``ACTUALIZACION`` value to reset cadence in months."""

        text = cls._normalized_text(value)
        if text is None:
            return None
        return cls._RESET_FREQUENCY_MONTHS.get(text)

    @classmethod
    def payment_day(cls, value: object) -> int | None:
        """Parse the governed ``Fecha Pago`` source value as a contractual day-of-month."""

        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            day = value
        elif isinstance(value, float):
            if not value.is_integer():
                return None
            day = int(value)
        else:
            text = str(value).strip()
            if not text:
                return None
            try:
                decimal_value = Decimal(text.replace(",", "."))
            except InvalidOperation:
                return None
            if decimal_value != decimal_value.to_integral_value():
                return None
            day = int(decimal_value)
        return day if 1 <= day <= 31 else None

    @classmethod
    def next_monthly_repricing_date(
        cls,
        *,
        cutoff_date: date,
        payment_day: object,
        update_frequency: object,
    ) -> date | None:
        """Derive the next monthly reset date after cutoff when the date exists exactly.

        The institution confirmed that repricing occurs on ``Fecha Pago`` and that
        ``ACTUALIZACION`` governs cadence. For multi-month cadences, the workbook
        still needs a schedule-phase anchor before an exact next reset month can be
        certified, so this method intentionally returns ``None`` for those cases.
        """

        frequency_months = cls.reset_frequency_months(update_frequency)
        day = cls.payment_day(payment_day)
        if frequency_months != 1 or day is None:
            return None

        if cutoff_date.month == 12:
            year = cutoff_date.year + 1
            month = 1
        else:
            year = cutoff_date.year
            month = cutoff_date.month + 1
        if day > monthrange(year, month)[1]:
            return None
        return date(year, month, day)

    @staticmethod
    def _normalized_text(value: object) -> str | None:
        if value is None:
            return None
        text = " ".join(str(value).replace("\u00a0", " ").split()).upper()
        return text or None
