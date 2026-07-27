from __future__ import annotations

from dataclasses import dataclass

from aip.domain.instruments.issuers.credit_rating import CreditRating
from aip.domain.instruments.issuers.issuer_type import IssuerType


@dataclass(frozen=True, slots=True)
class Issuer:
    """Issuer aggregate root value object."""

    code: str
    name: str
    issuer_type: IssuerType
    credit_rating: CreditRating | None = None
