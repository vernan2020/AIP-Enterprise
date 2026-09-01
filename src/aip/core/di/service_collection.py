"""Service collection for building dependency injection configuration.

The service collection acts as a builder for registering services before
the container is built and used for dependency resolution.
"""

from collections.abc import Callable
from typing import Any, TypeVar, overload

from .exceptions import ServiceAlreadyRegisteredError
from .lifetimes import ServiceLifetime
from .service_descriptor import ServiceDescriptor

T = TypeVar("T")
"""Type variable for service instances."""


class ServiceCollection:
    """Collection of service registrations for DI container configuration.

    Implements the builder pattern to register services with different lifetimes
    and factory strategies. Services are registered once and then used to build
    the service provider.

    Attributes:
        _services: Dictionary mapping service types to their descriptors.
    """

    def __init__(self) -> None:
        """Initialize an empty service collection."""
        self._services: dict[type, ServiceDescriptor] = {}

    @overload
    def add_singleton(self, service_type: type[T]) -> "ServiceCollection":
        """Register a singleton service."""
        ...

    @overload
    def add_singleton(
        self,
        service_type: type[T],
        implementation_type: type[T],
    ) -> "ServiceCollection":
        """Register a singleton service with implementation type."""
        ...

    @overload
    def add_singleton(
        self,
        service_type: type[T],
        factory: Callable[..., T],
    ) -> "ServiceCollection":
        """Register a singleton service with factory function."""
        ...

    def add_singleton(
        self,
        service_type: type[T],
        implementation_type: Any = None,
    ) -> "ServiceCollection":
        """Register a singleton service.

        A singleton service is instantiated once and reused throughout the
        application lifetime. Thread-safe singleton resolution is guaranteed.

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type or factory function. If None,
                service_type is used as implementation.

        Returns:
            Self for method chaining.

        Raises:
            ServiceAlreadyRegisteredError: If the service type is already registered.
        """
        return self._add_service(
            service_type,
            implementation_type,
            ServiceLifetime.SINGLETON,
        )

    @overload
    def add_transient(self, service_type: type[T]) -> "ServiceCollection":
        """Register a transient service."""
        ...

    @overload
    def add_transient(
        self,
        service_type: type[T],
        implementation_type: type[T],
    ) -> "ServiceCollection":
        """Register a transient service with implementation type."""
        ...

    @overload
    def add_transient(
        self,
        service_type: type[T],
        factory: Callable[..., T],
    ) -> "ServiceCollection":
        """Register a transient service with factory function."""
        ...

    def add_transient(
        self,
        service_type: type[T],
        implementation_type: Any = None,
    ) -> "ServiceCollection":
        """Register a transient service.

        A transient service creates a new instance each time it is requested.
        No caching occurs; each resolution creates a new object.

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type or factory function. If None,
                service_type is used as implementation.

        Returns:
            Self for method chaining.

        Raises:
            ServiceAlreadyRegisteredError: If the service type is already registered.
        """
        return self._add_service(
            service_type,
            implementation_type,
            ServiceLifetime.TRANSIENT,
        )

    @overload
    def add_scoped(self, service_type: type[T]) -> "ServiceCollection":
        """Register a scoped service."""
        ...

    @overload
    def add_scoped(
        self,
        service_type: type[T],
        implementation_type: type[T],
    ) -> "ServiceCollection":
        """Register a scoped service with implementation type."""
        ...

    @overload
    def add_scoped(
        self,
        service_type: type[T],
        factory: Callable[..., T],
    ) -> "ServiceCollection":
        """Register a scoped service with factory function."""
        ...

    def add_scoped(
        self,
        service_type: type[T],
        implementation_type: Any = None,
    ) -> "ServiceCollection":
        """Register a scoped service.

        A scoped service creates one instance per defined scope. This is useful
        for services that should be shared within a logical boundary (e.g., per request).

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type or factory function. If None,
                service_type is used as implementation.

        Returns:
            Self for method chaining.

        Raises:
            ServiceAlreadyRegisteredError: If the service type is already registered.
        """
        return self._add_service(
            service_type,
            implementation_type,
            ServiceLifetime.SCOPED,
        )

    def _add_service(
        self,
        service_type: type[T],
        implementation_type: type[T] | Callable[..., T] | None,
        lifetime: ServiceLifetime,
    ) -> "ServiceCollection":
        """Internal method to add a service to the collection.

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type or factory function.
            lifetime: Service lifetime strategy.

        Returns:
            Self for method chaining.

        Raises:
            ServiceAlreadyRegisteredError: If the service type is already registered.
        """
        if service_type in self._services:
            raise ServiceAlreadyRegisteredError(service_type)

        # Determine if implementation_type is a factory or a type
        factory = None
        impl_type = service_type

        if implementation_type is not None:
            if isinstance(implementation_type, type):
                impl_type = implementation_type
            else:
                # Assume it's a callable factory
                factory = implementation_type

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=impl_type,
            lifetime=lifetime,
            factory=factory,
        )

        self._services[service_type] = descriptor
        return self

    def try_add_singleton(self, service_type: type[T]) -> "ServiceCollection":
        """Try to register a singleton service, ignore if already registered.

        Args:
            service_type: The abstract service interface.

        Returns:
            Self for method chaining.
        """
        if service_type not in self._services:
            self.add_singleton(service_type)
        return self

    def try_add_transient(self, service_type: type[T]) -> "ServiceCollection":
        """Try to register a transient service, ignore if already registered.

        Args:
            service_type: The abstract service interface.

        Returns:
            Self for method chaining.
        """
        if service_type not in self._services:
            self.add_transient(service_type)
        return self

    def try_add_scoped(self, service_type: type[T]) -> "ServiceCollection":
        """Try to register a scoped service, ignore if already registered.

        Args:
            service_type: The abstract service interface.

        Returns:
            Self for method chaining.
        """
        if service_type not in self._services:
            self.add_scoped(service_type)
        return self

    def contains(self, service_type: type) -> bool:
        """Check if a service type is registered.

        Args:
            service_type: The service type to check.

        Returns:
            True if the service is registered, False otherwise.
        """
        return service_type in self._services

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()

    def get_descriptors(self) -> dict[type, ServiceDescriptor]:
        """Get all registered service descriptors.

        Returns:
            Dictionary mapping service types to descriptors.
        """
        return self._services.copy()

    def __len__(self) -> int:
        """Return the number of registered services.

        Returns:
            Count of registered services.
        """
        return len(self._services)

    def __repr__(self) -> str:
        """Return string representation of the service collection.

        Returns:
            String describing registered services.
        """
        service_list = "\n  ".join(str(descriptor) for descriptor in self._services.values())
        return f"ServiceCollection(\n  {service_list}\n)"
