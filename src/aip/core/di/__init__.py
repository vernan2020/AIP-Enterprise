"""Dependency injection framework package.

Provides a comprehensive dependency injection container for managing
service registration and resolution with support for multiple lifetimes,
circular dependency detection, and thread-safe operations.

Example:
    Basic usage:

    ```python
    from aip.core.di import Container

    class GreeterService:
        def greet(self, name: str) -> str:
            return f"Hello, {name}!"

    # Register and build
    container = Container()
    container.add_singleton(GreeterService)
    container.build()

    # Resolve
    greeter = container.resolve(GreeterService)
    print(greeter.greet("World"))
    ```

    With constructor injection:

    ```python
    class Logger:
        def log(self, message: str) -> None:
            print(f"[LOG] {message}")

    class Repository:
        def __init__(self, logger: Logger) -> None:
            self.logger = logger

        def fetch(self) -> None:
            self.logger.log("Fetching data...")

    container = Container()
    container.add_singleton(Logger)
    container.add_singleton(Repository)
    container.build()

    repo = container.resolve(Repository)
    repo.fetch()
    ```
"""

from .container import Container
from .exceptions import (
    CircularDependencyError,
    DIException,
    InvalidServiceDescriptorError,
    ResolutionError,
    ScopeNotActiveError,
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
)
from .lifetimes import ServiceLifetime
from .service_collection import ServiceCollection
from .service_descriptor import ServiceDescriptor
from .service_provider import DefaultServiceScope, ServiceProvider, ServiceScope

__all__ = [
    # Container
    "Container",
    # Collections and Providers
    "ServiceCollection",
    "ServiceProvider",
    "ServiceScope",
    "DefaultServiceScope",
    # Descriptors
    "ServiceDescriptor",
    # Lifetimes
    "ServiceLifetime",
    # Exceptions
    "DIException",
    "ServiceNotFoundError",
    "CircularDependencyError",
    "ServiceAlreadyRegisteredError",
    "ResolutionError",
    "InvalidServiceDescriptorError",
    "ScopeNotActiveError",
]

__version__ = "1.0.0"
