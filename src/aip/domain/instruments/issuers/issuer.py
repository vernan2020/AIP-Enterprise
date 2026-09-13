from __future__ import annotations

from dataclasses import dataclass

from .credit_rating import CreditRating
from .issuer_type import IssuerType


@dataclass(frozen=True, slots=True)
class Issuer:
    """Issuer aggregate root value object."""

    code: str
    name: str
    issuer_type: IssuerType
    credit_rating: CreditRating | None = None
