from __future__ import annotations


class CoopealianzaLiquidityError(Exception):
    """Base exception for the Coopealianza liquidity extension."""


class InstitutionalConfigurationError(CoopealianzaLiquidityError):
    """Raised when institutional configuration is invalid."""


class InstitutionalPolicyError(CoopealianzaLiquidityError):
    """Raised when an institutional policy cannot be evaluated."""


class InstitutionalProviderError(CoopealianzaLiquidityError):
    """Raised when an extension provider fails or returns malformed data."""


class PolicyReportError(CoopealianzaLiquidityError):
    """Raised when a liquidity policy report cannot be built."""
