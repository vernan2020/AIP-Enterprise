"""Unit tests for service descriptors."""

import pytest

from aip.core.di.lifetimes import ServiceLifetime
from aip.core.di.service_descriptor import ServiceDescriptor


class TestServiceDescriptor:
    """Tests for ServiceDescriptor class."""

    def test_service_descriptor_basic_creation(self) -> None:
        """Test basic service descriptor creation."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService)
        assert descriptor.service_type is MyService
        assert descriptor.implementation_type is MyService
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT
        assert descriptor.factory is None

    def test_service_descriptor_with_implementation_type(self) -> None:
        """Test service descriptor with different implementation type."""
        class IService:
            pass

        class MyService(IService):
            pass

        descriptor = ServiceDescriptor(IService, MyService)
        assert descriptor.service_type is IService
        assert descriptor.implementation_type is MyService

    def test_service_descriptor_with_lifetime(self) -> None:
        """Test service descriptor with specific lifetime."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(
            MyService,
            lifetime=ServiceLifetime.SINGLETON,
        )
        assert descriptor.lifetime == ServiceLifetime.SINGLETON

    def test_service_descriptor_with_factory(self) -> None:
        """Test service descriptor with factory function."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        descriptor = ServiceDescriptor(MyService, factory=factory)
        assert descriptor.factory is factory
        assert descriptor.has_factory()

    def test_service_descriptor_validation_no_factory(self) -> None:
        """Test descriptor validation with no factory and no explicit implementation."""
        class MyService:
            pass

        # This should succeed - service_type defaults to implementation_type
        descriptor = ServiceDescriptor(MyService, implementation_type=None, factory=None)
        assert descriptor.implementation_type is MyService

    def test_service_descriptor_validation_factory_type_error(self) -> None:
        """Test descriptor validation with both no implementation and factory."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        # This should succeed - factory is provided
        descriptor = ServiceDescriptor(MyService, implementation_type=None, factory=factory)
        assert descriptor.has_factory()

    def test_service_descriptor_validation_invalid_lifetime(self) -> None:
        """Test descriptor validation with invalid lifetime type."""
        class MyService:
            pass

        with pytest.raises(ValueError) as exc_info:
            ServiceDescriptor(MyService, lifetime="invalid")  # type: ignore
        assert "lifetime must be a ServiceLifetime instance" in str(exc_info.value)

    def test_service_descriptor_lifetime_checks(self) -> None:
        """Test lifetime checking methods."""
        class MyService:
            pass

        singleton_desc = ServiceDescriptor(
            MyService,
            lifetime=ServiceLifetime.SINGLETON,
        )
        assert singleton_desc.is_singleton()
        assert not singleton_desc.is_transient()
        assert not singleton_desc.is_scoped()

        transient_desc = ServiceDescriptor(
            MyService,
            lifetime=ServiceLifetime.TRANSIENT,
        )
        assert not transient_desc.is_singleton()
        assert transient_desc.is_transient()
        assert not transient_desc.is_scoped()

        scoped_desc = ServiceDescriptor(
            MyService,
            lifetime=ServiceLifetime.SCOPED,
        )
        assert not scoped_desc.is_singleton()
        assert not scoped_desc.is_transient()
        assert scoped_desc.is_scoped()

    def test_service_descriptor_has_factory(self) -> None:
        """Test factory presence detection."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        descriptor_with_factory = ServiceDescriptor(MyService, factory=factory)
        descriptor_without_factory = ServiceDescriptor(MyService)

        assert descriptor_with_factory.has_factory()
        assert not descriptor_without_factory.has_factory()

    def test_service_descriptor_repr(self) -> None:
        """Test string representation."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService)
        repr_str = repr(descriptor)
        assert "ServiceDescriptor" in repr_str
        assert "MyService" in repr_str
        assert "transient" in repr_str

    def test_service_descriptor_equality(self) -> None:
        """Test descriptor equality."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        desc1 = ServiceDescriptor(ServiceA)
        desc2 = ServiceDescriptor(ServiceA)
        desc3 = ServiceDescriptor(ServiceB)

        assert desc1 == desc2
        assert desc1 != desc3

    def test_service_descriptor_equality_with_non_descriptor(self) -> None:
        """Test descriptor equality with non-descriptor."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService)
        assert descriptor != "not a descriptor"
        assert descriptor != 42
        assert descriptor is not None

    def test_service_descriptor_hash(self) -> None:
        """Test descriptor hashing."""
        class MyService:
            pass

        descriptor = ServiceDescriptor(MyService)
        hash_value = hash(descriptor)
        assert isinstance(hash_value, int)

    def test_service_descriptor_can_be_dict_key(self) -> None:
        """Test descriptor can be used as dictionary key."""
        class ServiceA:
            pass

        class ServiceB:
            pass

        desc_a = ServiceDescriptor(ServiceA)
        desc_b = ServiceDescriptor(ServiceB)

        mapping = {desc_a: "service_a", desc_b: "service_b"}
        assert mapping[desc_a] == "service_a"
        assert mapping[desc_b] == "service_b"

    def test_service_descriptor_factory_and_implementation(self) -> None:
        """Test descriptor with both factory and implementation type."""
        class MyService:
            pass

        def factory() -> MyService:
            return MyService()

        # Factory takes precedence
        descriptor = ServiceDescriptor(
            MyService,
            implementation_type=MyService,
            factory=factory,
        )
        assert descriptor.has_factory()
        assert descriptor.factory is factory
