from aip.core.exceptions import ValidationError


class InstrumentError(ValidationError):
    """Base exception for instrument domain errors."""

    default_code = "INSTRUMENT_ERROR"


class InstrumentValidationError(InstrumentError):
    """Raised when an instrument fails validation rules."""

    default_code = "INSTRUMENT_VALIDATION_ERROR"
