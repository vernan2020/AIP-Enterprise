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
BORROWING_QUARTERLY_PHASE_RULE_REFERENCE = (
    "aip://irrbb/source-rules/borrowings/opening-date-quarterly-reset-phase/v1"
)
BORROWING_NEXT_RESET_RULE_REFERENCE = "aip://irrbb/source-rules/borrowings/next-repricing-date/v2"


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
    def next_repricing_date(
        cls,
        *,
        cutoff_date: date,
        payment_day: object,
        update_frequency: object,
        opening_date: date | None = None,
    ) -> date | None:
        """Derive the next governed repricing date strictly after ``cutoff_date``.

        Monthly positions reprice on ``Fecha Pago`` in the month immediately after
        the monthly cutoff. Quarterly positions use ``Fecha Apertura`` as the phase
        anchor: each three-month period is counted from the opening month and the
        repricing becomes effective in the following month, on ``Fecha Pago``.
        Unsupported cadences, missing anchors, or impossible calendar days fail closed.
        """

        frequency_months = cls.reset_frequency_months(update_frequency)
        day = cls.payment_day(payment_day)
        if day is None or frequency_months is None:
            return None

        if frequency_months == 1:
            year, month = cls._shift_year_month(cutoff_date.year, cutoff_date.month, 1)
            return cls._exact_calendar_date(year=year, month=month, day=day)

        if frequency_months != 3 or opening_date is None:
            return None

        first_repricing_ordinal = cls._month_ordinal(opening_date.year, opening_date.month) + 4
        cutoff_ordinal = cls._month_ordinal(cutoff_date.year, cutoff_date.month)

        if cutoff_ordinal <= first_repricing_ordinal:
            candidate_ordinal = first_repricing_ordinal
        else:
            elapsed_months = cutoff_ordinal - first_repricing_ordinal
            candidate_ordinal = first_repricing_ordinal + (elapsed_months // 3) * 3
            if candidate_ordinal < cutoff_ordinal:
                candidate_ordinal += 3

        year, month = cls._year_month_from_ordinal(candidate_ordinal)
        candidate = cls._exact_calendar_date(year=year, month=month, day=day)
        if candidate is None:
            return None
        if candidate <= cutoff_date:
            year, month = cls._year_month_from_ordinal(candidate_ordinal + 3)
            candidate = cls._exact_calendar_date(year=year, month=month, day=day)
        return candidate

    @classmethod
    def next_monthly_repricing_date(
        cls,
        *,
        cutoff_date: date,
        payment_day: object,
        update_frequency: object,
    ) -> date | None:
        """Compatibility wrapper for the governed monthly repricing rule."""

        if cls.reset_frequency_months(update_frequency) != 1:
            return None
        return cls.next_repricing_date(
            cutoff_date=cutoff_date,
            payment_day=payment_day,
            update_frequency=update_frequency,
        )

    @staticmethod
    def _month_ordinal(year: int, month: int) -> int:
        return year * 12 + (month - 1)

    @staticmethod
    def _year_month_from_ordinal(ordinal: int) -> tuple[int, int]:
        year, month_zero_based = divmod(ordinal, 12)
        return year, month_zero_based + 1

    @classmethod
    def _shift_year_month(cls, year: int, month: int, months: int) -> tuple[int, int]:
        return cls._year_month_from_ordinal(cls._month_ordinal(year, month) + months)

    @staticmethod
    def _exact_calendar_date(*, year: int, month: int, day: int) -> date | None:
        if day > monthrange(year, month)[1]:
            return None
        return date(year, month, day)

    @staticmethod
    def _normalized_text(value: object) -> str | None:
        if value is None:
            return None
        text = " ".join(str(value).replace("\u00a0", " ").split()).upper()
        return text or None
