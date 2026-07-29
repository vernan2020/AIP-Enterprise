"""Service descriptor for dependency injection container.

A service descriptor contains metadata about a service including its type,
implementation, lifetime, and factory function (if applicable).
"""

from collections.abc import Callable
from typing import Generic, TypeVar

from .lifetimes import ServiceLifetime

T = TypeVar("T")
"""Type variable for service instances."""


class ServiceDescriptor(Generic[T]):
    """Describes how to create and manage service instances.

    A descriptor holds metadata about a service including its abstract type,
    concrete implementation, lifetime strategy, and factory function for
    creating instances.

    Attributes:
        service_type: The abstract interface or base type.
        implementation_type: The concrete type to instantiate.
        lifetime: How long instances should persist.
        factory: Optional factory function for creating instances.
    """

    def __init__(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        factory: Callable[..., T] | None = None,
    ) -> None:
        """Initialize ServiceDescriptor.

        Args:
            service_type: The abstract interface or service type.
            implementation_type: Concrete type to instantiate. Defaults to service_type.
            lifetime: Service lifetime strategy.
            factory: Optional factory function for custom instance creation.

        Raises:
            ValueError: If both implementation_type and factory are None,
                or if factory and implementation_type are mutually exclusive.
        """
        self.service_type = service_type
        self.implementation_type = implementation_type or service_type
        self.lifetime = lifetime
        self.factory = factory

        self._validate()

    def _validate(self) -> None:
        """Validate the descriptor configuration.

        Raises:
            ValueError: If the descriptor configuration is invalid.
        """
        if self.factory is None and self.implementation_type is None:
            raise ValueError(
                "Either implementation_type or factory must be provided"
            )

        if not isinstance(self.lifetime, ServiceLifetime):
            raise ValueError(
                f"lifetime must be a ServiceLifetime instance, "
                f"got {type(self.lifetime).__name__}"
            )

    def has_factory(self) -> bool:
        """Check if descriptor uses a factory function.

        Returns:
            True if factory is provided, False otherwise.
        """
        return self.factory is not None

    def is_singleton(self) -> bool:
        """Check if service has singleton lifetime.

        Returns:
            True if lifetime is SINGLETON.
        """
        return self.lifetime == ServiceLifetime.SINGLETON

    def is_transient(self) -> bool:
        """Check if service has transient lifetime.

        Returns:
            True if lifetime is TRANSIENT.
        """
        return self.lifetime == ServiceLifetime.TRANSIENT

    def is_scoped(self) -> bool:
        """Check if service has scoped lifetime.

        Returns:
            True if lifetime is SCOPED.
        """
        return self.lifetime == ServiceLifetime.SCOPED

    def __repr__(self) -> str:
        """Return string representation of the descriptor.

        Returns:
            String describing the service descriptor.
        """
        impl_name = (
            self.implementation_type.__name__
            if self.implementation_type
            else "factory"
        )
        return (
            f"ServiceDescriptor("
            f"service={self.service_type.__name__}, "
            f"implementation={impl_name}, "
            f"lifetime={self.lifetime})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare two service descriptors.

        Args:
            other: Another ServiceDescriptor instance.

        Returns:
            True if descriptors describe the same service.
        """
        if not isinstance(other, ServiceDescriptor):
            return NotImplemented
        return (
            self.service_type == other.service_type
            and self.implementation_type == other.implementation_type
            and self.lifetime == other.lifetime
            and self.factory == other.factory
        )

    def __hash__(self) -> int:
        """Return hash of the descriptor.

        Returns:
            Hash value based on service type.
        """
        return hash(self.service_type)
