from __future__ import annotations

from datetime import date
from typing import Any


class PortfolioSecurityIdentityService:
    """Construye la identidad institucional estable de un título valor.

    Jerarquía:
    1. ISIN cuando está disponible.
    2. Serie + emisor + vencimiento como llave de respaldo.

    Este contrato se comparte entre VeR y sensibilidad para evitar que
    distintas capas agrupen el mismo título de forma diferente.
    """

    @classmethod
    def from_position(cls, position: dict[str, Any]) -> str:
        return cls.build(
            isin=str(position.get("isin") or "").strip(),
            series=str(
                position.get("series") or position.get("series_or_security_code") or ""
            ).strip(),
            issuer=str(position.get("issuer") or "").strip(),
            maturity_date=cls._as_date(
                position.get("maturity_date") or position.get("maturity_date_if_present")
            ),
        )

    @staticmethod
    def build(
        *,
        isin: str,
        series: str,
        issuer: str,
        maturity_date: date | None,
    ) -> str:
        normalized_isin = isin.strip().casefold()
        if normalized_isin:
            return f"isin:{normalized_isin}"

        maturity_text = maturity_date.isoformat() if maturity_date is not None else ""
        return (
            f"series:{series.strip().casefold()}"
            f"|issuer:{issuer.strip().casefold()}"
            f"|maturity:{maturity_text}"
        )

    @staticmethod
    def _as_date(value: object) -> date | None:
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
