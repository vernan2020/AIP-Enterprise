"""Domain exceptions for the portfolio bounded context."""


class PortfolioError(Exception):
    """Base exception for portfolio domain errors."""


class PortfolioClosedError(PortfolioError):
    """Raised when a closed portfolio receives a mutating operation."""


class DuplicatePositionError(PortfolioError):
    """Raised when a duplicate position business key is detected."""


class PositionNotFoundError(PortfolioError):
    """Raised when a position is not found in the portfolio."""


class InvalidTransactionError(PortfolioError):
    """Raised when transaction invariants are violated."""


class InvalidPositionError(PortfolioError):
    """Raised when position invariants are violated."""
