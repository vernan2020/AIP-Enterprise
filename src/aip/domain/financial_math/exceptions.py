from __future__ import annotations


class FinancialMathError(Exception):
    """Base domain exception for financial mathematics."""


class InvalidRateError(FinancialMathError):
    """Raised when a rate is invalid or would make a discount factor undefined."""


class InvalidCashFlowError(FinancialMathError):
    """Raised when cash flows are structurally invalid."""


class CurrencyMismatchError(FinancialMathError):
    """Raised when cash flows with incompatible currencies are combined."""


class ConvergenceError(FinancialMathError):
    """Raised when a solver cannot converge to a root."""


class InvalidBracketError(FinancialMathError):
    """Raised when a root-finding bracket is invalid."""


class CurveConstructionError(FinancialMathError):
    """Raised when a curve cannot be constructed."""


class InterpolationError(FinancialMathError):
    """Raised when interpolation is requested outside supported bounds."""


class BootstrapError(FinancialMathError):
    """Raised when bootstrap calibration fails."""
