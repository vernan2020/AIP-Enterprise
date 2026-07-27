"""Service provider for dependency resolution.

The service provider resolves service dependencies using registered descriptors,
handles different lifetime strategies, detects circular dependencies, and
manages singleton instances with thread-safe access.
"""

import inspect
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar, get_type_hints

from .exceptions import (
    CircularDependencyError,
    ResolutionError,
    ScopeNotActiveError,
    ServiceNotFoundError,
)
from .lifetimes import ServiceLifetime
from .service_descriptor import ServiceDescriptor

T = TypeVar("T")
"""Type variable for service instances."""


class ServiceScope(ABC):
    """Abstract base class for managing scoped service instances."""

    @abstractmethod
    def get_instance(
        self, service_type: type[T], instance: T
    ) -> T:
        """Get or cache scoped instance.

        Args:
            service_type: The service type.
            instance: The instance to store or retrieve.

        Returns:
            The scoped instance.
        """
        pass

    @abstractmethod
    def dispose(self) -> None:
        """Dispose of scoped resources."""
        pass


class DefaultServiceScope(ServiceScope):
    """Default implementation of service scope.

    Manages scoped service instances within a defined scope lifetime.
    """

    def __init__(self) -> None:
        """Initialize the service scope."""
        self._instances: dict[type, Any] = {}
        self._lock = threading.RLock()

    def get_instance(
        self, service_type: type[T], instance: T | None = None
    ) -> T:
        """Get or cache scoped instance.

        Args:
            service_type: The service type.
            instance: The instance to store if not cached.

        Returns:
            The scoped instance.
        """
        with self._lock:
            if service_type not in self._instances:
                if instance is None:
                    raise ValueError("Instance must be provided for new scope entry")
                self._instances[service_type] = instance
            return self._instances[service_type]

    def dispose(self) -> None:
        """Dispose of scoped resources."""
        with self._lock:
            self._instances.clear()


class ServiceProvider(Generic[T]):
    """Resolves service dependencies with support for multiple lifetimes.

    The service provider handles dependency resolution for registered services,
    manages instance caching for singleton and scoped services, detects
    circular dependencies, and supports lazy initialization.

    Thread-safe singleton resolution is guaranteed through synchronization.

    Attributes:
        _descriptors: Service descriptors by type.
        _singletons: Cached singleton instances.
        _current_scope: Thread-local storage for active scopes.
        _lock: Reentrant lock for thread-safe operations.
    """

    def __init__(self, descriptors: dict[type, ServiceDescriptor]) -> None:
        """Initialize the service provider.

        Args:
            descriptors: Dictionary of service descriptors by type.
        """
        self._descriptors = descriptors
        self._singletons: dict[type, Any] = {}
        self._lock = threading.RLock()
        self._scope_stack: threading.local = threading.local()

    def resolve(self, service_type: type[T]) -> T:
        """Resolve a service instance.

        Resolves the requested service, handling different lifetimes:
        - SINGLETON: Returns cached instance or creates once
        - TRANSIENT: Creates new instance each time
        - SCOPED: Returns instance for current scope or creates new

        Args:
            service_type: The type of service to resolve.

        Returns:
            An instance of the service.

        Raises:
            ServiceNotFoundError: If service type is not registered.
            CircularDependencyError: If circular dependency is detected.
            ScopeNotActiveError: If resolving scoped service outside scope.
            ResolutionError: If resolution fails for other reasons.
        """
        return self._resolve_internal(service_type, set())

    def _resolve_internal(
        self,
        service_type: type[T],
        visited: set[type],
    ) -> T:
        """Internal resolution with circular dependency detection.

        Args:
            service_type: The type of service to resolve.
            visited: Set of types currently being resolved (for cycle detection).

        Returns:
            An instance of the service.

        Raises:
            ServiceNotFoundError: If service type is not registered.
            CircularDependencyError: If circular dependency is detected.
            ScopeNotActiveError: If resolving scoped service outside scope.
            ResolutionError: If resolution fails.
        """
        if service_type not in self._descriptors:
            raise ServiceNotFoundError(service_type)

        # Detect circular dependencies
        if service_type in visited:
            chain = list(visited) + [service_type]
            chain_names = [t.__name__ for t in chain]
            raise CircularDependencyError(service_type, chain_names)

        descriptor = self._descriptors[service_type]

        # Handle singleton lifetime
        if descriptor.is_singleton():
            return self._resolve_singleton(descriptor, visited)

        # Handle scoped lifetime
        if descriptor.is_scoped():
            return self._resolve_scoped(descriptor, visited)

        # Handle transient lifetime
        return self._resolve_transient(descriptor, visited)

    def _resolve_singleton(
        self,
        descriptor: ServiceDescriptor,
        visited: set[type],
    ) -> T:
        """Resolve singleton service with thread-safe caching.

        Args:
            descriptor: The service descriptor.
            visited: Set of currently resolving types.

        Returns:
            The singleton instance.
        """
        with self._lock:
            if descriptor.service_type not in self._singletons:
                instance = self._create_instance(descriptor, visited)
                self._singletons[descriptor.service_type] = instance
            return self._singletons[descriptor.service_type]

    def _resolve_scoped(
        self,
        descriptor: ServiceDescriptor,
        visited: set[type],
    ) -> T:
        """Resolve scoped service within active scope.

        Args:
            descriptor: The service descriptor.
            visited: Set of currently resolving types.

        Returns:
            The scoped instance.

        Raises:
            ScopeNotActiveError: If no active scope exists.
        """
        scope = self._get_current_scope()
        if scope is None:
            raise ScopeNotActiveError(descriptor.service_type)

        # Check if instance exists in scope
        if descriptor.service_type in scope._instances:
            return scope._instances[descriptor.service_type]

        # Create new instance for this scope
        instance = self._create_instance(descriptor, visited)
        return scope.get_instance(descriptor.service_type, instance)

    def _resolve_transient(
        self,
        descriptor: ServiceDescriptor,
        visited: set[type],
    ) -> T:
        """Resolve transient service creating new instance.

        Args:
            descriptor: The service descriptor.
            visited: Set of currently resolving types.

        Returns:
            A new instance.
        """
        return self._create_instance(descriptor, visited)

    def _create_instance(
        self,
        descriptor: ServiceDescriptor,
        visited: set[type],
    ) -> T:
        """Create a service instance.

        Creates an instance using either a factory function or constructor
        injection with automatic dependency resolution.

        Args:
            descriptor: The service descriptor.
            visited: Set of currently resolving types.

        Returns:
            The created instance.

        Raises:
            ResolutionError: If instance creation fails.
        """
        try:
            # Use factory if provided
            if descriptor.has_factory():
                return descriptor.factory()  # type: ignore

            # Use constructor injection
            impl_type = descriptor.implementation_type
            return self._construct_with_dependencies(impl_type, visited)
        except Exception as exc:
            if isinstance(exc, (ServiceNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(
                descriptor.service_type,
                str(exc),
            ) from exc

    def _construct_with_dependencies(
        self,
        impl_type: type[T],
        visited: set[type],
    ) -> T:
        """Construct instance with automatic dependency injection.

        Inspects the constructor signature and resolves all required
        dependencies, injecting them as arguments.

        Args:
            impl_type: The implementation type to instantiate.
            visited: Set of currently resolving types.

        Returns:
            The constructed instance.

        Raises:
            ResolutionError: If constructor has unresolvable parameters.
        """
        try:
            sig = inspect.signature(impl_type.__init__)
            kwargs: dict[str, Any] = {}

            # Add service_type to visited to detect cycles
            new_visited = visited | {impl_type}

            # Try to resolve type hints including forward references
            try:
                type_hints = get_type_hints(impl_type.__init__)
            except Exception:
                # Fallback if get_type_hints fails
                type_hints = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Skip *args and **kwargs
                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue

                # Skip parameters with defaults
                if param.default is not inspect.Parameter.empty:
                    continue

                # Get type hint - prefer from get_type_hints (resolves forward refs)
                if param_name in type_hints:
                    param_type = type_hints[param_name]
                elif param.annotation is not inspect.Parameter.empty:
                    param_type = param.annotation
                else:
                    raise ResolutionError(
                        impl_type,
                        f"Parameter '{param_name}' missing type annotation",
                    )

                # If param_type is a string, try to resolve it from registered services
                if isinstance(param_type, str):
                    # Look through registered services for a type with this name
                    resolved = False
                    for service_type in self._descriptors.keys():
                        if service_type.__name__ == param_type:
                            param_type = service_type
                            resolved = True
                            break
                    if not resolved:
                        raise ResolutionError(
                            impl_type,
                            f"Cannot resolve forward reference '{param_type}'",
                        )

                kwargs[param_name] = self._resolve_internal(
                    param_type,
                    new_visited,
                )

            return impl_type(**kwargs)  # type: ignore
        except (ResolutionError, CircularDependencyError, ServiceNotFoundError):
            raise
        except Exception as exc:
            raise ResolutionError(
                impl_type,
                f"Constructor injection failed: {str(exc)}",
            ) from exc

    def create_scope(self) -> ServiceScope:
        """Create a new service scope for scoped services.

        Returns:
            A new service scope.
        """
        return DefaultServiceScope()

    def begin_scope(self, scope: ServiceScope) -> None:
        """Begin a new service scope.

        Args:
            scope: The scope to activate.
        """
        if not hasattr(self._scope_stack, "stack"):
            self._scope_stack.stack = []
        self._scope_stack.stack.append(scope)

    def end_scope(self) -> None:
        """End the current service scope."""
        if hasattr(self._scope_stack, "stack") and self._scope_stack.stack:
            scope = self._scope_stack.stack.pop()
            scope.dispose()

    def _get_current_scope(self) -> ServiceScope | None:
        """Get the currently active scope.

        Returns:
            The active scope or None if no scope is active.
        """
        if hasattr(self._scope_stack, "stack") and self._scope_stack.stack:
            return self._scope_stack.stack[-1]
        return None

    def __enter__(self) -> "ServiceProvider[T]":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        pass

    def __repr__(self) -> str:
        """Return string representation.

        Returns:
            String describing the service provider.
        """
        return (
            f"ServiceProvider("
            f"services={len(self._descriptors)}, "
            f"singletons={len(self._singletons)})"
        )
