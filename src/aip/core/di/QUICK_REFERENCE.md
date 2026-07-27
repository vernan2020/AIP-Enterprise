"""Dependency Injection Framework - Quick Reference Guide"""

# IMPORT
from aip.core.di import (
    Container,
    ServiceLifetime,
    ServiceNotFoundError,
    CircularDependencyError,
    ScopeNotActiveError,
)

# ============================================================================
# BASIC SETUP
# ============================================================================

# Create container
container = Container()

# Register services
container.add_singleton(ServiceA)
container.add_transient(ServiceB)
container.add_scoped(ServiceC)

# Build container
container.build()

# ============================================================================
# RESOLUTION
# ============================================================================

# Resolve singleton
service_a = container.resolve(ServiceA)

# Resolve transient
service_b = container.resolve(ServiceB)

# Resolve scoped (requires active scope)
with container.begin_scope() as provider:
    service_c = provider.resolve(ServiceC)

# ============================================================================
# REGISTRATION PATTERNS
# ============================================================================

# Type-to-type registration
container.add_singleton(IRepository, SqlRepository)

# With factory function
def create_config() -> Config:
    return Config(api_key="...")

container.add_singleton_factory(Config, create_config)

# Conditional registration (no error if already registered)
container.try_add_singleton(Logger)

# ============================================================================
# LIFETIMES EXPLAINED
# ============================================================================

# SINGLETON
# - One instance per application
# - Shared across all resolutions
# - Thread-safe creation
# Use for: expensive-to-create objects, shared state

# TRANSIENT
# - New instance every time
# - No caching
# Use for: stateless services, lightweight objects

# SCOPED
# - One instance per scope
# - Created once per scope
# Use for: request-scoped data, transaction objects

# ============================================================================
# CONSTRUCTOR INJECTION
# ============================================================================

# Types must be annotated for injection
class Repository:
    def __init__(self, logger: Logger, cache: Cache) -> None:
        self.logger = logger
        self.cache = cache

# Automatic injection on resolution
repo = container.resolve(Repository)
# → Logger and Cache are automatically resolved and injected

# Optional parameters with defaults are skipped
class Service:
    def __init__(self, logger: Logger, timeout: int = 30) -> None:
        self.logger = logger
        self.timeout = timeout

# ============================================================================
# ERROR HANDLING
# ============================================================================

# Service not found
try:
    container.resolve(UnregisteredService)
except ServiceNotFoundError as e:
    print(f"Service not found: {e}")

# Circular dependency
try:
    container.resolve(ServiceA)  # A → B → A
except CircularDependencyError as e:
    print(f"Circular dependency: {e}")

# Scoped service outside scope
try:
    container.resolve(ScopedService)  # No active scope
except ScopeNotActiveError as e:
    print(f"No active scope: {e}")

# ============================================================================
# ADVANCED PATTERNS
# ============================================================================

# Complex dependency tree
class Logger:
    pass

class Database:
    pass

class Cache:
    pass

class Repository:
    def __init__(self, db: Database, cache: Cache, log: Logger) -> None:
        self.db = db
        self.cache = cache
        self.log = log

class UserService:
    def __init__(self, repo: Repository, log: Logger) -> None:
        self.repo = repo
        self.log = log

# All dependencies automatically resolved
container.add_singleton(Logger)
container.add_singleton(Database)
container.add_singleton(Cache)
container.add_singleton(Repository)
container.add_singleton(UserService)
container.build()

user_service = container.resolve(UserService)

# ============================================================================
# SCOPE MANAGEMENT
# ============================================================================

# Create scope context
with container.begin_scope() as provider:
    scoped1 = provider.resolve(ScopedService)
    scoped2 = provider.resolve(ScopedService)
    assert scoped1 is scoped2  # Same instance

# Different scope
with container.begin_scope() as provider:
    scoped3 = provider.resolve(ScopedService)
    assert scoped1 is not scoped3  # Different instance

# Nested scopes
with container.begin_scope() as outer:
    service1 = outer.resolve(ScopedService)
    
    with container.begin_scope() as inner:
        service2 = inner.resolve(ScopedService)
        assert service1 is not service2

# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

# Simple factory
def create_logger() -> Logger:
    logger = Logger()
    logger.setup_handlers()
    return logger

container.add_singleton_factory(Logger, create_logger)

# Factory with dependencies
def create_repository(logger: Logger) -> IRepository:
    return SqlRepository(connection_string="...", logger=logger)

container.add_singleton_factory(IRepository, create_repository)

# ============================================================================
# TYPE HINTS REFERENCE
# ============================================================================

# String forward references are supported
class ServiceA:
    def __init__(self, service_b: "ServiceB") -> None:
        self.service_b = service_b

class ServiceB:
    pass

# Generic types supported
from typing import Generic, TypeVar

T = TypeVar("T")

class Repository(Generic[T]):
    pass

# Complex type hints supported
from typing import List, Optional

class Service:
    def __init__(self, items: List[str], config: Optional[Config] = None) -> None:
        pass

# ============================================================================
# BEST PRACTICES
# ============================================================================

# ✓ DO: Register all services before building
container = Container()
container.add_singleton(ServiceA)
container.add_singleton(ServiceB)
container.build()

# ✗ DON'T: Try to register after building
# container.add_singleton(ServiceC)  # RuntimeError

# ✓ DO: Use type annotations for all constructor parameters
class Service:
    def __init__(self, logger: Logger) -> None:
        pass

# ✗ DON'T: Skip type annotations
# class Service:
#     def __init__(self, logger):  # ResolutionError

# ✓ DO: Use scopes for request-scoped objects
with container.begin_scope() as provider:
    request_service = provider.resolve(RequestHandler)

# ✗ DON'T: Resolve scoped services outside scope
# scoped = container.resolve(ScopedService)  # ScopeNotActiveError

# ✓ DO: Use interfaces for loose coupling
class IRepository(ABC):
    @abstractmethod
    def fetch(self) -> str:
        pass

class SqlRepository(IRepository):
    def fetch(self) -> str:
        return "data"

container.add_singleton(IRepository, SqlRepository)

# ✓ DO: Use factories for complex initialization
def create_db_connection() -> Connection:
    conn = Connection(...)
    conn.open()
    return conn

container.add_singleton_factory(Connection, create_db_connection)

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Problem: ServiceNotFoundError
# Solution: Ensure service is registered before building
container.add_singleton(MyService)  # Add this
container.build()

# Problem: CircularDependencyError
# Solution: Refactor to break cycle, use factory, or use different design
# Option 1: Use factory to defer dependency creation
# Option 2: Inject interface instead of concrete type
# Option 3: Use property-based injection instead

# Problem: ScopeNotActiveError
# Solution: Use context manager for scoped services
with container.begin_scope() as provider:
    service = provider.resolve(ScopedService)

# Problem: Type annotation missing
# Solution: Add type hints to constructor parameters
class Repository:
    def __init__(self, logger: Logger) -> None:  # Add ': Logger'
        self.logger = logger

# Problem: Can't resolve forward reference
# Solution: Ensure the referenced class is registered
class A:
    def __init__(self, b: "B") -> None:
        self.b = b

class B:
    pass

container.add_singleton(A)
container.add_singleton(B)  # B must be registered for "B" to resolve

# ============================================================================
# PERFORMANCE TIPS
# ============================================================================

# Use SINGLETON for:
# - Services that are expensive to create
# - Stateless services that can be shared
# - Configuration objects
# - Database connections (connection pooling)

# Use TRANSIENT for:
# - Lightweight objects
# - Stateful objects that shouldn't be shared
# - DTOs and data containers

# Use SCOPED for:
# - Request-scoped handlers
# - Transaction objects
# - Request-specific state
# - Per-operation instances

# ============================================================================
# EXAMPLE: WEB APPLICATION
# ============================================================================

# Application setup
class Logger:
    pass

class Database:
    pass

class UserRepository:
    def __init__(self, db: Database, logger: Logger) -> None:
        self.db = db
        self.logger = logger

class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

# Setup container
app_container = Container()
app_container.add_singleton(Logger)
app_container.add_singleton(Database)
app_container.add_singleton(UserRepository)
app_container.add_singleton(UserService)
app_container.build()

# Request handling
def handle_request():
    with app_container.begin_scope() as provider:
        service = provider.resolve(UserService)
        user = service.repo.fetch_user(1)
        return user

# ============================================================================
# AVAILABLE EXCEPTIONS
# ============================================================================

ServiceNotFoundError       # Service type not registered
CircularDependencyError    # Circular dependency detected
ServiceAlreadyRegisteredError  # Duplicate registration
ResolutionError           # Resolution failed for any reason
InvalidServiceDescriptorError  # Descriptor configuration invalid
ScopeNotActiveError       # Scoped service outside scope
DIException               # Base exception for all DI errors

# ============================================================================
# CONTAINER API SUMMARY
# ============================================================================

# Registration methods
container.add_singleton(type, implementation)
container.add_transient(type, implementation)
container.add_scoped(type, implementation)
container.add_singleton_factory(type, factory_func)
container.add_transient_factory(type, factory_func)
container.add_scoped_factory(type, factory_func)
container.try_add_singleton(type)
container.try_add_transient(type)
container.try_add_scoped(type)

# Lifecycle methods
container.build()  # Build service provider
container.resolve(type)  # Resolve single service
container.begin_scope()  # Context manager for scoped services
container.get_provider()  # Get underlying service provider
container.is_built()  # Check if built

# Query methods
container._collection.contains(type)  # Check if type registered
container._collection.get_descriptors()  # Get all descriptors
len(container._collection)  # Number of registered services

# ============================================================================
# END OF QUICK REFERENCE
# ============================================================================
