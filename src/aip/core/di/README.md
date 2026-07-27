# Dependency Injection Framework

A comprehensive, enterprise-grade dependency injection framework for Python 3.13+ that implements SOLID principles and follows Clean Architecture patterns.

## Features

- **Multiple Lifetimes**
  - `SINGLETON`: Single instance shared across the application
  - `TRANSIENT`: New instance created each time
  - `SCOPED`: Single instance per defined scope

- **Constructor Injection**: Automatic dependency resolution through type-hinted constructors
- **Circular Dependency Detection**: Automatic detection and reporting of circular dependencies
- **Thread-Safe Singleton Resolution**: Guaranteed thread-safe singleton creation
- **Factory Functions**: Support for custom factory functions for complex object creation
- **Forward References**: Support for string type hints and forward references
- **Service Scopes**: Context managers for managing scoped service lifetimes

## Architecture

### Components

#### `exceptions.py`
Custom exception classes for DI operations:
- `DIException`: Base exception
- `ServiceNotFoundError`: Service not registered
- `CircularDependencyError`: Circular dependency detected
- `ServiceAlreadyRegisteredError`: Duplicate registration attempt
- `ResolutionError`: Resolution failure
- `InvalidServiceDescriptorError`: Invalid descriptor configuration
- `ScopeNotActiveError`: Scoped service outside active scope

#### `lifetimes.py`
`ServiceLifetime` enumeration defining service lifetimes:
- `SINGLETON`
- `TRANSIENT`
- `SCOPED`

#### `service_descriptor.py`
`ServiceDescriptor` class that holds metadata about a service:
- Service type and implementation type
- Lifetime strategy
- Optional factory function
- Validation and query methods

#### `service_collection.py`
`ServiceCollection` class implementing the builder pattern:
- Fluent API for service registration
- Support for different registration methods
- Try-add operations for conditional registration
- Method chaining

#### `service_provider.py`
`ServiceProvider` class responsible for dependency resolution:
- Service resolution with circular dependency detection
- Automatic constructor injection
- Thread-safe singleton caching
- Scope management
- Forward reference resolution

#### `container.py`
`Container` class - the main public API:
- Fluent interface for service registration
- Automatic service provider building
- Scope management through context managers
- Registration and resolution lifecycle control

## Usage Examples

### Basic Registration and Resolution

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

### Constructor Injection

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
repo.fetch()  # Output: [LOG] Fetching data...
```

### Different Lifetimes

```python
class SingletonService:
    pass

class TransientService:
    pass

class ScopedService:
    pass

container = Container()
container.add_singleton(SingletonService)
container.add_transient(TransientService)
container.add_scoped(ScopedService)
container.build()

# Singleton: same instance
s1 = container.resolve(SingletonService)
s2 = container.resolve(SingletonService)
assert s1 is s2  # True

# Transient: different instances
t1 = container.resolve(TransientService)
t2 = container.resolve(TransientService)
assert t1 is not t2  # True

# Scoped: same within scope, different across scopes
with container.begin_scope() as provider:
    sc1 = provider.resolve(ScopedService)
    sc2 = provider.resolve(ScopedService)
    assert sc1 is sc2  # True

with container.begin_scope() as provider:
    sc3 = provider.resolve(ScopedService)
    assert sc1 is not sc3  # True
```

### Factory Functions

```python
class Configuration:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

def config_factory() -> Configuration:
    # Load from environment or config file
    api_key = "your-api-key"
    return Configuration(api_key)

container = Container()
container.add_singleton_factory(Configuration, config_factory)
container.build()

config = container.resolve(Configuration)
```

### Interface-Based Registration

```python
from abc import ABC, abstractmethod

class IRepository(ABC):
    @abstractmethod
    def fetch(self) -> str:
        pass

class SqlRepository(IRepository):
    def fetch(self) -> str:
        return "Data from SQL"

container = Container()
container.add_singleton(IRepository, SqlRepository)
container.build()

repo = container.resolve(IRepository)
assert isinstance(repo, SqlRepository)
```

### Complex Dependency Trees

```python
class Database:
    pass

class Cache:
    pass

class Logger:
    pass

class Repository:
    def __init__(
        self,
        database: Database,
        cache: Cache,
        logger: Logger,
    ) -> None:
        self.database = database
        self.cache = cache
        self.logger = logger

class Service:
    def __init__(self, repository: Repository, logger: Logger) -> None:
        self.repository = repository
        self.logger = logger

container = Container()
container.add_singleton(Database)
container.add_singleton(Cache)
container.add_singleton(Logger)
container.add_singleton(Repository)
container.add_singleton(Service)
container.build()

service = container.resolve(Service)
# All dependencies are automatically resolved and injected
```

## Error Handling

### Circular Dependency Detection

```python
class ServiceA:
    def __init__(self, service_b: "ServiceB") -> None:
        self.service_b = service_b

class ServiceB:
    def __init__(self, service_a: ServiceA) -> None:
        self.service_a = service_a

container = Container()
container.add_singleton(ServiceA)
container.add_singleton(ServiceB)
container.build()

try:
    container.resolve(ServiceA)
except CircularDependencyError as e:
    print(f"Circular dependency detected: {e}")
```

### Missing Service

```python
from aip.core.di import ServiceNotFoundError

class UnregisteredService:
    pass

container = Container()
container.build()

try:
    container.resolve(UnregisteredService)
except ServiceNotFoundError as e:
    print(f"Service not found: {e}")
```

## SOLID Principles

The framework is designed following SOLID principles:

- **S** (Single Responsibility): Each class has a single, well-defined purpose
- **O** (Open/Closed): Open for extension through factory functions and custom scopes
- **L** (Liskov Substitution): Supports interface-based registration and injection
- **I** (Interface Segregation): Small, focused interfaces for each component
- **D** (Dependency Inversion): Depends on abstractions, not concrete implementations

## Thread Safety

- **Singleton Resolution**: Thread-safe through reentrant locking
- **Service Scopes**: Thread-local storage for scope management
- **Concurrent Access**: Multiple threads can safely resolve services simultaneously

## Best Practices

1. **Register all services before calling `build()`**
   ```python
   container = Container()
   container.add_singleton(ServiceA)
   container.add_singleton(ServiceB)
   container.build()  # No registrations after this point
   ```

2. **Use type hints for all constructor parameters**
   ```python
   # Good
   class Service:
       def __init__(self, logger: Logger) -> None:
           self.logger = logger

   # Bad - will cause ResolutionError
   class Service:
       def __init__(self, logger):
           self.logger = logger
   ```

3. **Use scopes for request-scoped services**
   ```python
   with container.begin_scope() as provider:
       # Scoped services are managed within this context
       service = provider.resolve(ScopedService)
   ```

4. **Use factories for complex initialization**
   ```python
   def create_service() -> ComplexService:
       # Custom initialization logic
       return ComplexService(...)

   container.add_singleton_factory(ComplexService, create_service)
   ```

5. **Avoid circular dependencies**
   - Use dependency inversion (interfaces)
   - Refactor to break cycles
   - Use factory functions if necessary

## Testing

The framework includes comprehensive unit tests covering:

- Service descriptor creation and validation
- Service collection registration
- Service provider resolution
- Circular dependency detection
- Thread-safe singleton resolution
- Constructor injection
- Scoped services
- Factory functions
- Error handling

Run tests with:
```bash
pytest tests/unit/core/di/ -v
```

## Performance Considerations

- **Singleton Creation**: Thread-safe lock acquired once per singleton
- **Transient Resolution**: Minimal overhead, simple object creation
- **Constructor Injection**: Reflection overhead during resolution (not cached)
- **Scoped Services**: Efficient cache lookup within scope

For optimal performance:
- Use singletons for expensive-to-create services
- Use scopes for request-scoped operations
- Minimize constructor parameter count
- Consider factory functions for complex initialization

## Version

1.0.0 - Enterprise-grade DI framework for Python 3.13+

## License

Proprietary - Coopealianza R.L.
