"""Validation framework for AIP Enterprise.

This module provides validation utilities including validators and guard clauses
for enforcing business rules and data integrity across the application.

Classes:
    Guard: Assertion-style validation methods.
    Validators: Collection of reusable validation functions.
"""

import sys

from aip.shared.validation.exceptions import (
    InvalidFormatError,
    NotEmptyError,
    PositiveValueError,
    RangeError,
    RequiredValueError,
    ValidationException,
)
from aip.shared.validation.validators import (
    Guard,
    Validators,
)

sys.modules.setdefault("src.aip.shared.validation", sys.modules[__name__])

__all__ = [
    "ValidationException",
    "RequiredValueError",
    "PositiveValueError",
    "NotEmptyError",
    "RangeError",
    "InvalidFormatError",
    "Guard",
    "Validators",
]
