"""Dependency injection framework exceptions.

This module provides custom exception classes for the dependency injection
container, handling various error scenarios during service resolution.
"""


class DIException(Exception):
    """Base exception for dependency injection framework."""

    pass


class ServiceNotFoundError(DIException):
    """Raised when a requested service is not registered in the container."""

    def __init__(self, service_type: type, message: str | None = None) -> None:
        """Initialize ServiceNotFoundError.

        Args:
            service_type: The type of service that was not found.
            message: Optional custom error message.
        """
        self.service_type = service_type
        default_msg = f"Service of type '{service_type.__name__}' not found in container"
        super().__init__(message or default_msg)


class CircularDependencyError(DIException):
    """Raised when a circular dependency is detected during resolution."""

    def __init__(self, service_type: type, dependency_chain: list[str]) -> None:
        """Initialize CircularDependencyError.

        Args:
            service_type: The type that caused the circular dependency.
            dependency_chain: List of service names forming the circular chain.
        """
        self.service_type = service_type
        self.dependency_chain = dependency_chain
        chain_str = " -> ".join(dependency_chain)
        message = f"Circular dependency detected: {chain_str}"
        super().__init__(message)


class ServiceAlreadyRegisteredError(DIException):
    """Raised when attempting to register a service that already exists."""

    def __init__(self, service_type: type, message: str | None = None) -> None:
        """Initialize ServiceAlreadyRegisteredError.

        Args:
            service_type: The type of service already registered.
            message: Optional custom error message.
        """
        self.service_type = service_type
        default_msg = (
            f"Service of type '{service_type.__name__}' is already registered"
        )
        super().__init__(message or default_msg)


class ResolutionError(DIException):
    """Raised when service resolution fails for any reason."""

    def __init__(self, service_type: type, reason: str) -> None:
        """Initialize ResolutionError.

        Args:
            service_type: The type of service that failed to resolve.
            reason: The reason for the resolution failure.
        """
        self.service_type = service_type
        self.reason = reason
        message = (
            f"Failed to resolve service '{service_type.__name__}': {reason}"
        )
        super().__init__(message)


class InvalidServiceDescriptorError(DIException):
    """Raised when a service descriptor is invalid."""

    def __init__(self, message: str) -> None:
        """Initialize InvalidServiceDescriptorError.

        Args:
            message: Description of the validation error.
        """
        super().__init__(f"Invalid service descriptor: {message}")


class ScopeNotActiveError(DIException):
    """Raised when trying to resolve a scoped service outside of an active scope."""

    def __init__(self, service_type: type) -> None:
        """Initialize ScopeNotActiveError.

        Args:
            service_type: The scoped service type requested.
        """
        self.service_type = service_type
        message = (
            f"Cannot resolve scoped service '{service_type.__name__}' "
            "outside of an active scope"
        )
        super().__init__(message)
