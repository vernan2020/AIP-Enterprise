"""Unit tests for dependency injection container."""

import pytest

from aip.core.di import (
    Container,
    ServiceLifetime,
    ServiceNotFoundError,
    CircularDependencyError,
    ScopeNotActiveError,
)


class TestContainer:
    """Tests for Container class."""

    def test_container_creation(self) -> None:
        """Test container can be created."""
        container = Container()
        assert container is not None
        assert not container.is_built()

    def test_add_singleton(self) -> None:
        """Test adding singleton service."""
        class MyService:
            pass

        container = Container()
        result = container.add_singleton(MyService)
        assert result is container

    def test_add_transient(self) -> None:
        """Test adding transient service."""
        class MyService:
            pass

        container = Container()
        result = container.add_transient(MyService)
        assert result is container

    def test_add_scoped(self) -> None:
        """Test adding scoped service."""
        class MyService:
            pass

        container = Container()
        result = container.add_scoped(MyService)
        assert result is container

    def test_add_singleton_factory(self) -> None:
        """Test adding singleton with factory."""
        class MyService:
            def __init__(self, value: int) -> None:
                self.value = value

        def factory() -> MyService:
            return MyService(42)

        container = Container()
        result = container.add_singleton_factory(MyService, factory)
        assert result is container

    def test_add_transient_factory(self) -> None:
        """Test adding transient with factory."""
        class MyService:
            def __init__(self, value: int) -> None:
                self.value = value

        def factory() -> MyService:
            return MyService(42)

        container = Container()
        result = container.add_transient_factory(MyService, factory)
        assert result is container

    def test_add_scoped_factory(self) -> None:
        """Test adding scoped with factory."""
        class MyService:
            def __init__(self, value: int) -> None:
                self.value = value

        def factory() -> MyService:
            return MyService(42)

        container = Container()
        result = container.add_scoped_factory(MyService, factory)
        assert result is container

    def test_method_chaining(self) -> None:
        """Test method chaining for fluent API."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        class ServiceC:
            pass

        container = (
            Container()
            .add_singleton(ServiceA)
            .add_transient(ServiceB)
            .add_scoped(ServiceC)
        )

        assert not container.is_built()

    def test_build_container(self) -> None:
        """Test building container."""
        class MyService:
            pass

        container = Container()
        container.add_singleton(MyService)

        result = container.build()
        assert result is container
        assert container.is_built()

    def test_build_empty_container_fails(self) -> None:
        """Test building empty container fails."""
        container = Container()

        with pytest.raises(ValueError) as exc_info:
            container.build()
        assert "No services registered" in str(exc_info.value)

    def test_register_after_build_fails(self) -> None:
        """Test registering service after build fails."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        container = Container()
        container.add_singleton(ServiceA)
        container.build()

        with pytest.raises(RuntimeError) as exc_info:
            container.add_singleton(ServiceB)
        assert "Cannot register" in str(exc_info.value)

    def test_resolve_singleton(self) -> None:
        """Test resolving singleton service."""
        class MyService:
            pass

        container = Container()
        container.add_singleton(MyService)
        container.build()

        instance1 = container.resolve(MyService)
        instance2 = container.resolve(MyService)

        assert instance1 is instance2

    def test_resolve_transient(self) -> None:
        """Test resolving transient service."""
        class MyService:
            pass

        container = Container()
        container.add_transient(MyService)
        container.build()

        instance1 = container.resolve(MyService)
        instance2 = container.resolve(MyService)

        assert instance1 is not instance2

    def test_resolve_with_constructor_injection(self) -> None:
        """Test resolving with constructor injection."""
        class Logger:
            pass

        class Repository:
            def __init__(self, logger: Logger) -> None:
                self.logger = logger

        container = Container()
        container.add_singleton(Logger)
        container.add_singleton(Repository)
        container.build()

        repo = container.resolve(Repository)
        assert isinstance(repo, Repository)
        assert isinstance(repo.logger, Logger)

    def test_resolve_without_build_fails(self) -> None:
        """Test resolving without building fails."""
        class MyService:
            pass

        container = Container()
        container.add_singleton(MyService)

        with pytest.raises(RuntimeError) as exc_info:
            container.resolve(MyService)
        assert "not built" in str(exc_info.value).lower()

    def test_resolve_unregistered_service_fails(self) -> None:
        """Test resolving unregistered service fails."""
        class RegisteredService:
            pass

        class UnregisteredService:
            pass

        container = Container()
        container.add_singleton(RegisteredService)
        container.build()

        with pytest.raises(ServiceNotFoundError):
            container.resolve(UnregisteredService)

    def test_resolve_circular_dependency_fails(self) -> None:
        """Test resolving circular dependency fails."""
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

        with pytest.raises(CircularDependencyError):
            container.resolve(ServiceA)

    def test_try_add_singleton(self) -> None:
        """Test try_add_singleton."""
        class MyService:
            pass

        container = Container()
        container.try_add_singleton(MyService)
        container.try_add_singleton(MyService)  # Should not fail

        assert not container.is_built()

    def test_try_add_transient(self) -> None:
        """Test try_add_transient."""
        class MyService:
            pass

        container = Container()
        container.try_add_transient(MyService)
        container.try_add_transient(MyService)  # Should not fail

    def test_try_add_scoped(self) -> None:
        """Test try_add_scoped."""
        class MyService:
            pass

        container = Container()
        container.try_add_scoped(MyService)
        container.try_add_scoped(MyService)  # Should not fail

    def test_scoped_resolution_without_scope_fails(self) -> None:
        """Test scoped resolution fails without scope."""
        class ScopedService:
            pass

        container = Container()
        container.add_scoped(ScopedService)
        container.build()

        with pytest.raises(ScopeNotActiveError):
            container.resolve(ScopedService)

    def test_scoped_resolution_with_scope(self) -> None:
        """Test scoped resolution within scope."""
        class ScopedService:
            pass

        container = Container()
        container.add_scoped(ScopedService)
        container.build()

        with container.begin_scope() as provider:
            instance1 = provider.resolve(ScopedService)
            instance2 = provider.resolve(ScopedService)
            assert instance1 is instance2

    def test_scoped_resolution_different_scopes(self) -> None:
        """Test scoped services are different across scopes."""
        class ScopedService:
            pass

        container = Container()
        container.add_scoped(ScopedService)
        container.build()

        with container.begin_scope() as provider:
            instance1 = provider.resolve(ScopedService)

        with container.begin_scope() as provider:
            instance2 = provider.resolve(ScopedService)

        assert instance1 is not instance2

    def test_complex_dependency_tree(self) -> None:
        """Test resolving complex dependency tree."""
        class Logger:
            pass

        class Database:
            pass

        class Cache:
            pass

        class Repository:
            def __init__(
                self,
                logger: Logger,
                database: Database,
                cache: Cache,
            ) -> None:
                self.logger = logger
                self.database = database
                self.cache = cache

        class Service:
            def __init__(self, repository: Repository, logger: Logger) -> None:
                self.repository = repository
                self.logger = logger

        container = Container()
        container.add_singleton(Logger)
        container.add_singleton(Database)
        container.add_singleton(Cache)
        container.add_singleton(Repository)
        container.add_singleton(Service)
        container.build()

        service = container.resolve(Service)
        assert isinstance(service, Service)
        assert isinstance(service.repository, Repository)
        assert isinstance(service.logger, Logger)
        assert service.logger is service.repository.logger

    def test_get_provider(self) -> None:
        """Test getting underlying service provider."""
        class MyService:
            pass

        container = Container()
        container.add_singleton(MyService)
        container.build()

        provider = container.get_provider()
        assert provider is not None

    def test_get_provider_before_build_fails(self) -> None:
        """Test getting provider before build fails."""
        container = Container()

        with pytest.raises(RuntimeError):
            container.get_provider()

    def test_repr_not_built(self) -> None:
        """Test string representation when not built."""
        class MyService:
            pass

        container = Container()
        container.add_singleton(MyService)

        repr_str = repr(container)
        assert "Container" in repr_str
        assert "built=False" in repr_str

    def test_repr_built(self) -> None:
        """Test string representation when built."""
        class MyService:
            pass

        container = Container()
        container.add_singleton(MyService)
        container.build()

        repr_str = repr(container)
        assert "Container" in repr_str
        assert "built=True" in repr_str

    def test_singleton_with_implementation_type(self) -> None:
        """Test singleton with different implementation type."""
        class IService:
            def get_name(self) -> str:
                raise NotImplementedError

        class MyService(IService):
            def get_name(self) -> str:
                return "MyService"

        container = Container()
        container.add_singleton(IService, MyService)
        container.build()

        instance = container.resolve(IService)
        assert isinstance(instance, MyService)
        assert instance.get_name() == "MyService"

    def test_mixed_lifetimes(self) -> None:
        """Test container with mixed service lifetimes."""
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

        singleton1 = container.resolve(SingletonService)
        singleton2 = container.resolve(SingletonService)
        assert singleton1 is singleton2

        transient1 = container.resolve(TransientService)
        transient2 = container.resolve(TransientService)
        assert transient1 is not transient2

        with container.begin_scope() as provider:
            scoped1 = provider.resolve(ScopedService)
            scoped2 = provider.resolve(ScopedService)
            assert scoped1 is scoped2
