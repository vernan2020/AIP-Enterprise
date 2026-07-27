"""Unit tests for service collection."""

import pytest

from aip.core.di.exceptions import ServiceAlreadyRegisteredError
from aip.core.di.lifetimes import ServiceLifetime
from aip.core.di.service_collection import ServiceCollection


class TestServiceCollection:
    """Tests for ServiceCollection class."""

    def test_service_collection_creation(self) -> None:
        """Test service collection can be created."""
        collection = ServiceCollection()
        assert len(collection) == 0

    def test_add_singleton_basic(self) -> None:
        """Test adding basic singleton service."""
        class MyService:
            pass

        collection = ServiceCollection()
        result = collection.add_singleton(MyService)
        assert result is collection  # Check method chaining
        assert len(collection) == 1
        assert collection.contains(MyService)

    def test_add_singleton_with_implementation(self) -> None:
        """Test adding singleton with different implementation type."""
        class IService:
            pass

        class MyService(IService):
            pass

        collection = ServiceCollection()
        collection.add_singleton(IService, MyService)
        assert collection.contains(IService)
        assert len(collection) == 1

    def test_add_singleton_with_factory(self) -> None:
        """Test adding singleton with factory function."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        collection = ServiceCollection()
        collection.add_singleton(MyService, factory)
        assert collection.contains(MyService)

    def test_add_transient_basic(self) -> None:
        """Test adding basic transient service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_transient(MyService)
        assert collection.contains(MyService)
        assert len(collection) == 1

    def test_add_transient_with_implementation(self) -> None:
        """Test adding transient with different implementation type."""
        class IService:
            pass

        class MyService(IService):
            pass

        collection = ServiceCollection()
        collection.add_transient(IService, MyService)
        assert collection.contains(IService)

    def test_add_transient_with_factory(self) -> None:
        """Test adding transient with factory function."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        collection = ServiceCollection()
        collection.add_transient(MyService, factory)
        assert collection.contains(MyService)

    def test_add_scoped_basic(self) -> None:
        """Test adding basic scoped service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_scoped(MyService)
        assert collection.contains(MyService)
        assert len(collection) == 1

    def test_add_scoped_with_implementation(self) -> None:
        """Test adding scoped with different implementation type."""
        class IService:
            pass

        class MyService(IService):
            pass

        collection = ServiceCollection()
        collection.add_scoped(IService, MyService)
        assert collection.contains(IService)

    def test_add_scoped_with_factory(self) -> None:
        """Test adding scoped with factory function."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        collection = ServiceCollection()
        collection.add_scoped(MyService, factory)
        assert collection.contains(MyService)

    def test_method_chaining(self) -> None:
        """Test method chaining for fluent API."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        class ServiceC:
            pass

        collection = (
            ServiceCollection()
            .add_singleton(ServiceA)
            .add_transient(ServiceB)
            .add_scoped(ServiceC)
        )

        assert len(collection) == 3
        assert collection.contains(ServiceA)
        assert collection.contains(ServiceB)
        assert collection.contains(ServiceC)

    def test_duplicate_registration_raises_error(self) -> None:
        """Test registering duplicate service raises error."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_singleton(MyService)

        with pytest.raises(ServiceAlreadyRegisteredError) as exc_info:
            collection.add_singleton(MyService)
        assert exc_info.value.service_type is MyService

    def test_try_add_singleton_new_service(self) -> None:
        """Test try_add_singleton adds new service."""
        class MyService:
            pass

        collection = ServiceCollection()
        result = collection.try_add_singleton(MyService)
        assert result is collection
        assert collection.contains(MyService)

    def test_try_add_singleton_existing_service(self) -> None:
        """Test try_add_singleton ignores existing service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_transient(MyService)
        collection.try_add_singleton(MyService)
        # Should still be transient, not singleton
        assert collection.contains(MyService)
        assert len(collection) == 1

    def test_try_add_transient_new_service(self) -> None:
        """Test try_add_transient adds new service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.try_add_transient(MyService)
        assert collection.contains(MyService)

    def test_try_add_transient_existing_service(self) -> None:
        """Test try_add_transient ignores existing service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_singleton(MyService)
        collection.try_add_transient(MyService)
        assert collection.contains(MyService)
        assert len(collection) == 1

    def test_try_add_scoped_new_service(self) -> None:
        """Test try_add_scoped adds new service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.try_add_scoped(MyService)
        assert collection.contains(MyService)

    def test_try_add_scoped_existing_service(self) -> None:
        """Test try_add_scoped ignores existing service."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_singleton(MyService)
        collection.try_add_scoped(MyService)
        assert collection.contains(MyService)
        assert len(collection) == 1

    def test_clear_collection(self) -> None:
        """Test clearing service collection."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        collection = (
            ServiceCollection()
            .add_singleton(ServiceA)
            .add_transient(ServiceB)
        )
        assert len(collection) == 2

        collection.clear()
        assert len(collection) == 0
        assert not collection.contains(ServiceA)
        assert not collection.contains(ServiceB)

    def test_get_descriptors(self) -> None:
        """Test getting all service descriptors."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        collection = ServiceCollection()
        collection.add_singleton(ServiceA)
        collection.add_transient(ServiceB)

        descriptors = collection.get_descriptors()
        assert len(descriptors) == 2
        assert ServiceA in descriptors
        assert ServiceB in descriptors
        assert descriptors[ServiceA].is_singleton()
        assert descriptors[ServiceB].is_transient()

    def test_descriptor_lifetime_persistence(self) -> None:
        """Test that descriptor lifetimes are preserved."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        class ServiceC:
            pass

        collection = ServiceCollection()
        collection.add_singleton(ServiceA)
        collection.add_transient(ServiceB)
        collection.add_scoped(ServiceC)

        descriptors = collection.get_descriptors()
        assert descriptors[ServiceA].lifetime == ServiceLifetime.SINGLETON
        assert descriptors[ServiceB].lifetime == ServiceLifetime.TRANSIENT
        assert descriptors[ServiceC].lifetime == ServiceLifetime.SCOPED

    def test_len_collection(self) -> None:
        """Test collection length."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        collection = ServiceCollection()
        assert len(collection) == 0

        collection.add_singleton(ServiceA)
        assert len(collection) == 1

        collection.add_transient(ServiceB)
        assert len(collection) == 2

    def test_repr_collection(self) -> None:
        """Test collection string representation."""
        class MyService:
            pass

        collection = ServiceCollection()
        collection.add_singleton(MyService)

        repr_str = repr(collection)
        assert "ServiceCollection" in repr_str
        assert "MyService" in repr_str
