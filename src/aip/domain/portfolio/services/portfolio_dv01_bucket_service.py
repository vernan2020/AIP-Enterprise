from __future__ import annotations

from datetime import date
from typing import Any


class PortfolioDV01BucketService:
    """Clasifica posiciones en los tramos institucionales de sensibilidad DV01."""

    @classmethod
    def bucket_key(
        cls,
        position: dict[str, Any],
        *,
        valuation_date: date,
    ) -> str | None:
        is_variable = str(position.get("variable_rate_flag") or "").strip().casefold() in {
            "s",
            "si",
            "sí",
            "yes",
            "y",
            "true",
            "1",
        }
        raw_date = (
            position.get("next_repricing_date") if is_variable else position.get("maturity_date")
        )
        reference_date = cls._as_date(raw_date)
        if reference_date is None:
            return None

        one_year = cls._advance_years(valuation_date, 1)
        five_years = cls._advance_years(valuation_date, 5)
        if reference_date < one_year:
            return "< 1 año"
        if reference_date <= five_years:
            return "1 a 5 años"
        return "> 5 años"

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _advance_years(value: date, years: int) -> date:
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(year=value.year + years, month=2, day=28)
