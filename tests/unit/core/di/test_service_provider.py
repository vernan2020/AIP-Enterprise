"""Unit tests for service provider."""

import pytest
import threading
from typing import Any

from aip.core.di.exceptions import (
    CircularDependencyError,
    ResolutionError,
    ScopeNotActiveError,
    ServiceNotFoundError,
)
from aip.core.di.lifetimes import ServiceLifetime
from aip.core.di.service_descriptor import ServiceDescriptor
from aip.core.di.service_provider import (
    ServiceProvider,
    DefaultServiceScope,
)


class TestServiceProvider:
    """Tests for ServiceProvider class."""

    def test_service_provider_creation(self) -> None:
        """Test service provider can be created."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService, lifetime=ServiceLifetime.SINGLETON)
        provider = ServiceProvider({MyService: descriptor})

        assert provider is not None

    def test_resolve_singleton(self) -> None:
        """Test resolving singleton service returns same instance."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService, lifetime=ServiceLifetime.SINGLETON)
        provider = ServiceProvider({MyService: descriptor})

        instance1 = provider.resolve(MyService)
        instance2 = provider.resolve(MyService)

        assert instance1 is instance2

    def test_resolve_transient(self) -> None:
        """Test resolving transient service creates new instances."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService, lifetime=ServiceLifetime.TRANSIENT)
        provider = ServiceProvider({MyService: descriptor})

        instance1 = provider.resolve(MyService)
        instance2 = provider.resolve(MyService)

        assert instance1 is not instance2

    def test_resolve_with_factory(self) -> None:
        """Test resolving service with factory function."""
        class MyService:
            def __init__(self, value: int) -> None:
                self.value = value

        def factory() -> MyService:
            return MyService(42)

        descriptor = ServiceDescriptor(
            MyService,
            factory=factory,
            lifetime=ServiceLifetime.SINGLETON,
        )
        provider = ServiceProvider({MyService: descriptor})

        instance = provider.resolve(MyService)
        assert instance.value == 42

    def test_resolve_service_not_found(self) -> None:
        """Test resolving unregistered service raises error."""
        class UnregisteredService:
            pass

        provider = ServiceProvider({})

        with pytest.raises(ServiceNotFoundError) as exc_info:
            provider.resolve(UnregisteredService)
        assert exc_info.value.service_type is UnregisteredService

    def test_constructor_injection_single_dependency(self) -> None:
        """Test constructor injection with single dependency."""
        class Logger:
            pass

        class Repository:
            def __init__(self, logger: Logger) -> None:
                self.logger = logger

        logger_desc = ServiceDescriptor(Logger, lifetime=ServiceLifetime.SINGLETON)
        repo_desc = ServiceDescriptor(Repository, lifetime=ServiceLifetime.SINGLETON)

        provider = ServiceProvider({Logger: logger_desc, Repository: repo_desc})

        repo = provider.resolve(Repository)
        assert isinstance(repo, Repository)
        assert isinstance(repo.logger, Logger)

    def test_constructor_injection_multiple_dependencies(self) -> None:
        """Test constructor injection with multiple dependencies."""
        class Logger:
            pass

        class Database:
            pass

        class Repository:
            def __init__(self, logger: Logger, database: Database) -> None:
                self.logger = logger
                self.database = database

        logger_desc = ServiceDescriptor(Logger)
        db_desc = ServiceDescriptor(Database)
        repo_desc = ServiceDescriptor(Repository)

        provider = ServiceProvider({
            Logger: logger_desc,
            Database: db_desc,
            Repository: repo_desc,
        })

        repo = provider.resolve(Repository)
        assert isinstance(repo.logger, Logger)
        assert isinstance(repo.database, Database)

    def test_constructor_injection_with_defaults(self) -> None:
        """Test constructor injection skips parameters with defaults."""
        class Logger:
            pass

        class Repository:
            def __init__(self, logger: Logger, name: str = "default") -> None:
                self.logger = logger
                self.name = name

        logger_desc = ServiceDescriptor(Logger)
        repo_desc = ServiceDescriptor(Repository)

        provider = ServiceProvider({Logger: logger_desc, Repository: repo_desc})

        repo = provider.resolve(Repository)
        assert isinstance(repo.logger, Logger)
        assert repo.name == "default"

    def test_constructor_injection_missing_type_annotation(self) -> None:
        """Test constructor injection fails with missing type annotation."""
        class Repository:
            def __init__(self, dependency):  # type: ignore
                self.dependency = dependency

        repo_desc = ServiceDescriptor(Repository)
        provider = ServiceProvider({Repository: repo_desc})

        with pytest.raises(ResolutionError) as exc_info:
            provider.resolve(Repository)
        assert "type annotation" in str(exc_info.value).lower()

    def test_circular_dependency_direct(self) -> None:
        """Test detection of direct circular dependency."""
        class ServiceA:
            def __init__(self, service_b: "ServiceB") -> None:
                self.service_b = service_b

        class ServiceB:
            def __init__(self, service_a: ServiceA) -> None:
                self.service_a = service_a

        service_a_desc = ServiceDescriptor(ServiceA)
        service_b_desc = ServiceDescriptor(ServiceB)

        provider = ServiceProvider({ServiceA: service_a_desc, ServiceB: service_b_desc})

        with pytest.raises(CircularDependencyError) as exc_info:
            provider.resolve(ServiceA)
        assert "ServiceA" in exc_info.value.dependency_chain
        assert "ServiceB" in exc_info.value.dependency_chain

    def test_circular_dependency_indirect(self) -> None:
        """Test detection of indirect circular dependency."""
        class ServiceA:
            def __init__(self, service_b: "ServiceB") -> None:
                self.service_b = service_b

        class ServiceB:
            def __init__(self, service_c: "ServiceC") -> None:
                self.service_c = service_c

        class ServiceC:
            def __init__(self, service_a: ServiceA) -> None:
                self.service_a = service_a

        service_a_desc = ServiceDescriptor(ServiceA)
        service_b_desc = ServiceDescriptor(ServiceB)
        service_c_desc = ServiceDescriptor(ServiceC)

        provider = ServiceProvider({
            ServiceA: service_a_desc,
            ServiceB: service_b_desc,
            ServiceC: service_c_desc,
        })

        with pytest.raises(CircularDependencyError):
            provider.resolve(ServiceA)

    def test_scoped_resolution_without_scope(self) -> None:
        """Test scoped resolution fails outside active scope."""
        class ScopedService:
            pass

        desc = ServiceDescriptor(ScopedService, lifetime=ServiceLifetime.SCOPED)
        provider = ServiceProvider({ScopedService: desc})

        with pytest.raises(ScopeNotActiveError):
            provider.resolve(ScopedService)

    def test_scoped_resolution_with_scope(self) -> None:
        """Test scoped resolution within active scope."""
        class ScopedService:
            pass

        desc = ServiceDescriptor(ScopedService, lifetime=ServiceLifetime.SCOPED)
        provider = ServiceProvider({ScopedService: desc})

        scope = provider.create_scope()
        provider.begin_scope(scope)

        try:
            instance1 = provider.resolve(ScopedService)
            instance2 = provider.resolve(ScopedService)
            assert instance1 is instance2
        finally:
            provider.end_scope()

    def test_nested_scopes(self) -> None:
        """Test nested service scopes."""
        class ScopedService:
            pass

        desc = ServiceDescriptor(ScopedService, lifetime=ServiceLifetime.SCOPED)
        provider = ServiceProvider({ScopedService: desc})

        scope1 = provider.create_scope()
        scope2 = provider.create_scope()

        provider.begin_scope(scope1)
        instance1 = provider.resolve(ScopedService)

        provider.begin_scope(scope2)
        instance2 = provider.resolve(ScopedService)

        provider.end_scope()
        provider.end_scope()

        assert instance1 is not instance2

    def test_thread_safe_singleton(self) -> None:
        """Test singleton resolution is thread-safe."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService, lifetime=ServiceLifetime.SINGLETON)
        provider = ServiceProvider({MyService: descriptor})

        instances: list[Any] = []
        lock = threading.Lock()

        def resolve_service() -> None:
            instance = provider.resolve(MyService)
            with lock:
                instances.append(instance)

        threads = [threading.Thread(target=resolve_service) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All instances should be the same
        first_instance = instances[0]
        assert all(inst is first_instance for inst in instances)

    def test_multiple_singleton_instances(self) -> None:
        """Test multiple singleton services maintain separate instances."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        desc_a = ServiceDescriptor(ServiceA, lifetime=ServiceLifetime.SINGLETON)
        desc_b = ServiceDescriptor(ServiceB, lifetime=ServiceLifetime.SINGLETON)

        provider = ServiceProvider({ServiceA: desc_a, ServiceB: desc_b})

        instance_a1 = provider.resolve(ServiceA)
        instance_b1 = provider.resolve(ServiceB)
        instance_a2 = provider.resolve(ServiceA)
        instance_b2 = provider.resolve(ServiceB)

        assert instance_a1 is instance_a2
        assert instance_b1 is instance_b2
        assert instance_a1 is not instance_b1

    def test_repr(self) -> None:
        """Test provider string representation."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        desc_a = ServiceDescriptor(ServiceA)
        desc_b = ServiceDescriptor(ServiceB)

        provider = ServiceProvider({ServiceA: desc_a, ServiceB: desc_b})
        repr_str = repr(provider)

        assert "ServiceProvider" in repr_str


class TestDefaultServiceScope:
    """Tests for DefaultServiceScope class."""

    def test_scope_creation(self) -> None:
        """Test service scope can be created."""
        scope = DefaultServiceScope()
        assert scope is not None

    def test_scope_get_instance_new(self) -> None:
        """Test getting new instance in scope."""
        class MyService:
            pass

        scope = DefaultServiceScope()
        instance = MyService()

        retrieved = scope.get_instance(MyService, instance)
        assert retrieved is instance

    def test_scope_get_instance_cached(self) -> None:
        """Test getting cached instance from scope."""
        class MyService:
            pass

        scope = DefaultServiceScope()
        instance1 = MyService()

        scope.get_instance(MyService, instance1)
        instance2 = MyService()
        retrieved = scope.get_instance(MyService, instance2)

        assert retrieved is instance1
        assert retrieved is not instance2

    def test_scope_dispose_clears_instances(self) -> None:
        """Test scope disposal clears instances."""
        class MyService:
            pass

        scope = DefaultServiceScope()
        instance = MyService()
        scope.get_instance(MyService, instance)

        scope.dispose()

        new_instance = MyService()
        retrieved = scope.get_instance(MyService, new_instance)
        assert retrieved is new_instance
