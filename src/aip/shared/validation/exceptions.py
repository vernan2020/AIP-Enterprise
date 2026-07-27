"""Validation exceptions for AIP Enterprise.

This module defines the exception hierarchy for validation errors,
providing domain-specific error types for different validation failures.
"""

from __future__ import annotations

import sys


class ValidationException(Exception):
    """Base exception for all validation errors."""
    
    def __init__(self, message: str, field_name: str | None = None) -> None:
        """Initialize validation exception.
        
        Args:
            message: The error message.
            field_name: Optional field name that failed validation.
        """
        super().__init__(message)
        self.message = message
        self.field_name = field_name


class RequiredValueError(ValidationException):
    """Raised when a required value is missing or None."""
    
    def __init__(self, field_name: str) -> None:
        """Initialize required value error.
        
        Args:
            field_name: The name of the required field.
        """
        message = f"Required value missing: {field_name}"
        super().__init__(message, field_name)


class PositiveValueError(ValidationException):
    """Raised when a value must be positive but is not."""
    
    def __init__(self, field_name: str, value: int | float) -> None:
        """Initialize positive value error.
        
        Args:
            field_name: The name of the field.
            value: The invalid value provided.
        """
        message = f"Value must be positive: {field_name}={value}"
        super().__init__(message, field_name)


class NotEmptyError(ValidationException):
    """Raised when a collection or string must not be empty."""
    
    def __init__(self, field_name: str) -> None:
        """Initialize not empty error.
        
        Args:
            field_name: The name of the field.
        """
        message = f"Value must not be empty: {field_name}"
        super().__init__(message, field_name)


class RangeError(ValidationException):
    """Raised when a value is outside valid range."""
    
    def __init__(
        self,
        field_name: str,
        value: int | float,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
    ) -> None:
        """Initialize range error.
        
        Args:
            field_name: The name of the field.
            value: The invalid value provided.
            min_value: The minimum acceptable value.
            max_value: The maximum acceptable value.
        """
        if min_value is not None and max_value is not None:
            message = (
                f"Value out of range: {field_name}={value}, "
                f"must be between {min_value} and {max_value}"
            )
        elif min_value is not None:
            message = f"Value out of range: {field_name}={value}, must be >= {min_value}"
        else:
            message = f"Value out of range: {field_name}={value}, must be <= {max_value}"
        
        super().__init__(message, field_name)


class InvalidFormatError(ValidationException):
    """Raised when a value has invalid format."""
    
    def __init__(self, field_name: str, expected_format: str) -> None:
        """Initialize invalid format error.
        
        Args:
            field_name: The name of the field.
            expected_format: Description of expected format.
        """
        message = f"Invalid format: {field_name}, expected {expected_format}"
        super().__init__(message, field_name)


sys.modules.setdefault("src.aip.shared.validation.exceptions", sys.modules[__name__])
