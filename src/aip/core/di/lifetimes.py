"""Service lifetime definitions for dependency injection container.

Lifetimes define how long a service instance persists and when new instances
are created. This module provides different lifetime options for services.
"""

from enum import Enum, auto


class ServiceLifetime(Enum):
    """Enumeration of service lifetime strategies.

    Attributes:
        SINGLETON: Single instance shared across the entire application lifetime.
        TRANSIENT: New instance created each time the service is requested.
        SCOPED: Single instance per defined scope (e.g., per request).
    """

    SINGLETON = auto()
    """Service instance is created once and reused throughout application lifetime."""

    TRANSIENT = auto()
    """New service instance is created each time it is requested."""

    SCOPED = auto()
    """Service instance is created once per scope and shared within that scope."""

    def __str__(self) -> str:
        """Return string representation of the lifetime.

        Returns:
            String name of the lifetime.
        """
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> "ServiceLifetime":
        """Create ServiceLifetime from string representation.

        Args:
            value: String representation of lifetime (case-insensitive).

        Returns:
            The corresponding ServiceLifetime.

        Raises:
            ValueError: If the string doesn't match any lifetime.
        """
        try:
            return cls[value.upper()]
        except KeyError:
            valid_values = ", ".join([item.name.lower() for item in cls])
            raise ValueError(f"Invalid lifetime: '{value}'. Must be one of: {valid_values}")
