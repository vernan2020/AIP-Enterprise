"""Unit tests for dependency injection exceptions."""

import pytest

from aip.core.di.exceptions import (
    CircularDependencyError,
    DIException,
    InvalidServiceDescriptorError,
    ResolutionError,
    ScopeNotActiveError,
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
)


class TestDIException:
    """Tests for DIException base class."""

    def test_di_exception_creation(self) -> None:
        """Test DIException can be created and raised."""
        exc = DIException("test message")
        assert str(exc) == "test message"

    def test_di_exception_inheritance(self) -> None:
        """Test DIException inherits from Exception."""
        assert issubclass(DIException, Exception)


class TestServiceNotFoundError:
    """Tests for ServiceNotFoundError."""

    def test_service_not_found_error_with_defaults(self) -> None:
        """Test ServiceNotFoundError with default message."""
        class MyService:
            pass

        exc = ServiceNotFoundError(MyService)
        assert "MyService" in str(exc)
        assert exc.service_type is MyService

    def test_service_not_found_error_with_custom_message(self) -> None:
        """Test ServiceNotFoundError with custom message."""
        class MyService:
            pass

        custom_msg = "Custom error"
        exc = ServiceNotFoundError(MyService, custom_msg)
        assert str(exc) == custom_msg

    def test_service_not_found_error_is_di_exception(self) -> None:
        """Test ServiceNotFoundError is a DIException."""
        assert issubclass(ServiceNotFoundError, DIException)


class TestCircularDependencyError:
    """Tests for CircularDependencyError."""

    def test_circular_dependency_error_creation(self) -> None:
        """Test CircularDependencyError with dependency chain."""
        class ServiceA:
            pass

        chain = ["ServiceA", "ServiceB", "ServiceA"]
        exc = CircularDependencyError(ServiceA, chain)
        assert exc.service_type is ServiceA
        assert exc.dependency_chain == chain
        assert "ServiceA -> ServiceB -> ServiceA" in str(exc)

    def test_circular_dependency_error_single_item_chain(self) -> None:
        """Test CircularDependencyError with single item chain."""
        class ServiceA:
            pass

        chain = ["ServiceA"]
        exc = CircularDependencyError(ServiceA, chain)
        assert "ServiceA" in str(exc)


class TestServiceAlreadyRegisteredError:
    """Tests for ServiceAlreadyRegisteredError."""

    def test_service_already_registered_error_with_defaults(self) -> None:
        """Test ServiceAlreadyRegisteredError with default message."""
        class MyService:
            pass

        exc = ServiceAlreadyRegisteredError(MyService)
        assert "MyService" in str(exc)
        assert "already registered" in str(exc)

    def test_service_already_registered_error_with_custom_message(self) -> None:
        """Test ServiceAlreadyRegisteredError with custom message."""
        class MyService:
            pass

        custom_msg = "Custom error"
        exc = ServiceAlreadyRegisteredError(MyService, custom_msg)
        assert str(exc) == custom_msg


class TestResolutionError:
    """Tests for ResolutionError."""

    def test_resolution_error_creation(self) -> None:
        """Test ResolutionError creation."""
        class MyService:
            pass

        exc = ResolutionError(MyService, "Invalid parameter")
        assert exc.service_type is MyService
        assert exc.reason == "Invalid parameter"
        assert "MyService" in str(exc)
        assert "Invalid parameter" in str(exc)


class TestInvalidServiceDescriptorError:
    """Tests for InvalidServiceDescriptorError."""

    def test_invalid_service_descriptor_error(self) -> None:
        """Test InvalidServiceDescriptorError creation."""
        exc = InvalidServiceDescriptorError("Descriptor is invalid")
        assert "Descriptor is invalid" in str(exc)
        assert "Invalid service descriptor" in str(exc)


class TestScopeNotActiveError:
    """Tests for ScopeNotActiveError."""

    def test_scope_not_active_error(self) -> None:
        """Test ScopeNotActiveError creation."""
        class ScopedService:
            pass

        exc = ScopeNotActiveError(ScopedService)
        assert exc.service_type is ScopedService
        assert "ScopedService" in str(exc)
        assert "active scope" in str(exc).lower()
