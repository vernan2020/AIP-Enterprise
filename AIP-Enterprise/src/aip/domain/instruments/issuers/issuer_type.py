from enum import Enum


class IssuerType(Enum):
    """Issuer categories."""

    GOVERNMENT = "government"
    CORPORATE = "corporate"
    BANK = "bank"
    FINANCIAL_INSTITUTION = "financial_institution"
