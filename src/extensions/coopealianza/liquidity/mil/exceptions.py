from __future__ import annotations


class CoopealianzaMilError(Exception):
    """Base exception for the Coopealianza MIL eligibility extension."""


class MilConfigurationError(CoopealianzaMilError):
    """Raised when MIL configuration is invalid."""


class MilEligibilityError(CoopealianzaMilError):
    """Raised when MIL eligibility cannot be determined."""


class MilCapacityError(CoopealianzaMilError):
    """Raised when MIL capacity calculations fail."""


class MilProviderError(CoopealianzaMilError):
    """Raised when MIL providers fail or return malformed data."""


class MilReportError(CoopealianzaMilError):
    """Raised when an MIL eligibility report cannot be built."""


class MilValuationError(CoopealianzaMilError):
    """Raised when MIL valuation cannot be validated."""


class MilConcentrationError(CoopealianzaMilError):
    """Raised when MIL concentration calculations fail."""
