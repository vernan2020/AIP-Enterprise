"""Dependency injection container for application bootstrapping.

The container provides a fluent API for configuring and building a dependency
injection system. It manages service registration and resolution through the
service collection and provider.
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TypeVar

from .service_collection import ServiceCollection
from .service_provider import ServiceProvider, ServiceScope
from .lifetimes import ServiceLifetime

T = TypeVar("T")
"""Type variable for service instances."""


class Container:
    """Main dependency injection container for application.

    The container provides a fluent API for service registration and resolution.
    It follows the builder pattern to configure services before building the
    provider, then switches to read-only resolution mode.

    Attributes:
        _collection: Service collection for registration phase.
        _provider: Service provider for resolution phase.
    """

    def __init__(self) -> None:
        """Initialize a new container."""
        self._collection = ServiceCollection()
        self._provider: ServiceProvider | None = None

    def add_singleton(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
    ) -> "Container":
        """Register a singleton service.

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type. Uses service_type if not provided.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.add_singleton(service_type, implementation_type)
        return self

    def add_singleton_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
    ) -> "Container":
        """Register a singleton service with factory function.

        Args:
            service_type: The abstract service interface.
            factory: Factory function to create instances.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.add_singleton(service_type, factory)
        return self

    def add_transient(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
    ) -> "Container":
        """Register a transient service.

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type. Uses service_type if not provided.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.add_transient(service_type, implementation_type)
        return self

    def add_transient_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
    ) -> "Container":
        """Register a transient service with factory function.

        Args:
            service_type: The abstract service interface.
            factory: Factory function to create instances.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.add_transient(service_type, factory)
        return self

    def add_scoped(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
    ) -> "Container":
        """Register a scoped service.

        Args:
            service_type: The abstract service interface.
            implementation_type: Concrete type. Uses service_type if not provided.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.add_scoped(service_type, implementation_type)
        return self

    def add_scoped_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
    ) -> "Container":
        """Register a scoped service with factory function.

        Args:
            service_type: The abstract service interface.
            factory: Factory function to create instances.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.add_scoped(service_type, factory)
        return self

    def try_add_singleton(self, service_type: type[T]) -> "Container":
        """Try to register singleton, ignore if already registered.

        Args:
            service_type: The abstract service interface.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.try_add_singleton(service_type)
        return self

    def try_add_transient(self, service_type: type[T]) -> "Container":
        """Try to register transient, ignore if already registered.

        Args:
            service_type: The abstract service interface.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.try_add_transient(service_type)
        return self

    def try_add_scoped(self, service_type: type[T]) -> "Container":
        """Try to register scoped, ignore if already registered.

        Args:
            service_type: The abstract service interface.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If container is already built.
        """
        self._ensure_not_built()
        self._collection.try_add_scoped(service_type)
        return self

    def build(self) -> "Container":
        """Build the service provider from registered services.

        After building, no new services can be registered. The container
        switches to read-only resolution mode.

        Returns:
            Self for chaining with resolve operations.

        Raises:
            ValueError: If no services are registered.
        """
        if self._provider is not None:
            raise RuntimeError("Container is already built")

        if len(self._collection) == 0:
            raise ValueError("No services registered in collection")

        descriptors = self._collection.get_descriptors()
        self._provider = ServiceProvider(descriptors)
        return self

    def resolve(self, service_type: type[T]) -> T:
        """Resolve a service instance.

        Args:
            service_type: The type of service to resolve.

        Returns:
            An instance of the service.

        Raises:
            RuntimeError: If container is not built.
        """
        self._ensure_built()
        return self._provider.resolve(service_type)

    def create_scope(self) -> ServiceScope:
        """Create a new service scope for scoped services.

        Returns:
            A new scope.

        Raises:
            RuntimeError: If container is not built.
        """
        self._ensure_built()
        return self._provider.create_scope()

    @contextmanager
    def begin_scope(self) -> Generator[ServiceProvider, None, None]:
        """Context manager for scoped service resolution.

        Example:
            ```python
            with container.begin_scope() as provider:
                scoped_service = provider.resolve(ScopedServiceType)
            ```

        Yields:
            Service provider with active scope.

        Raises:
            RuntimeError: If container is not built.
        """
        self._ensure_built()
        scope = self.create_scope()
        self._provider.begin_scope(scope)
        try:
            yield self._provider
        finally:
            self._provider.end_scope()

    def _ensure_built(self) -> None:
        """Ensure container is built before resolution.

        Raises:
            RuntimeError: If container is not built.
        """
        if self._provider is None:
            raise RuntimeError("Container not built. Call build() first.")

    def _ensure_not_built(self) -> None:
        """Ensure container is not built during registration.

        Raises:
            RuntimeError: If container is already built.
        """
        if self._provider is not None:
            raise RuntimeError("Cannot register services after container is built")

    def is_built(self) -> bool:
        """Check if container is built.

        Returns:
            True if built, False otherwise.
        """
        return self._provider is not None

    def get_provider(self) -> ServiceProvider:
        """Get the underlying service provider.

        Returns:
            The service provider instance.

        Raises:
            RuntimeError: If container is not built.
        """
        self._ensure_built()
        return self._provider

    def __repr__(self) -> str:
        """Return string representation.

        Returns:
            String describing the container state.
        """
        if self._provider is None:
            return f"Container(services={len(self._collection)}, built=False)"
        return f"Container({self._provider}, built=True)"
