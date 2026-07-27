"""Unit tests for service lifetimes."""

import pytest

from aip.core.di.lifetimes import ServiceLifetime


class TestServiceLifetime:
    """Tests for ServiceLifetime enumeration."""

    def test_service_lifetime_values(self) -> None:
        """Test all service lifetime values exist."""
        assert hasattr(ServiceLifetime, "SINGLETON")
        assert hasattr(ServiceLifetime, "TRANSIENT")
        assert hasattr(ServiceLifetime, "SCOPED")

    def test_service_lifetime_singleton(self) -> None:
        """Test SINGLETON lifetime."""
        assert ServiceLifetime.SINGLETON == ServiceLifetime.SINGLETON

    def test_service_lifetime_transient(self) -> None:
        """Test TRANSIENT lifetime."""
        assert ServiceLifetime.TRANSIENT == ServiceLifetime.TRANSIENT

    def test_service_lifetime_scoped(self) -> None:
        """Test SCOPED lifetime."""
        assert ServiceLifetime.SCOPED == ServiceLifetime.SCOPED

    def test_service_lifetime_string_representation(self) -> None:
        """Test string representation of lifetimes."""
        assert str(ServiceLifetime.SINGLETON) == "singleton"
        assert str(ServiceLifetime.TRANSIENT) == "transient"
        assert str(ServiceLifetime.SCOPED) == "scoped"

    def test_service_lifetime_from_string_lowercase(self) -> None:
        """Test creating lifetime from lowercase string."""
        assert ServiceLifetime.from_string("singleton") == ServiceLifetime.SINGLETON
        assert ServiceLifetime.from_string("transient") == ServiceLifetime.TRANSIENT
        assert ServiceLifetime.from_string("scoped") == ServiceLifetime.SCOPED

    def test_service_lifetime_from_string_uppercase(self) -> None:
        """Test creating lifetime from uppercase string."""
        assert ServiceLifetime.from_string("SINGLETON") == ServiceLifetime.SINGLETON
        assert ServiceLifetime.from_string("TRANSIENT") == ServiceLifetime.TRANSIENT
        assert ServiceLifetime.from_string("SCOPED") == ServiceLifetime.SCOPED

    def test_service_lifetime_from_string_mixed_case(self) -> None:
        """Test creating lifetime from mixed case string."""
        assert ServiceLifetime.from_string("SiNgLeToN") == ServiceLifetime.SINGLETON
        assert ServiceLifetime.from_string("TrAnSiEnT") == ServiceLifetime.TRANSIENT
        assert ServiceLifetime.from_string("ScOpEd") == ServiceLifetime.SCOPED

    def test_service_lifetime_from_string_invalid(self) -> None:
        """Test creating lifetime from invalid string raises error."""
        with pytest.raises(ValueError) as exc_info:
            ServiceLifetime.from_string("invalid")
        assert "Invalid lifetime" in str(exc_info.value)
        assert "singleton, transient, scoped" in str(exc_info.value)

    def test_service_lifetime_enum_properties(self) -> None:
        """Test service lifetime enum properties."""
        lifetimes = list(ServiceLifetime)
        assert len(lifetimes) == 3
        assert ServiceLifetime.SINGLETON in lifetimes
        assert ServiceLifetime.TRANSIENT in lifetimes
        assert ServiceLifetime.SCOPED in lifetimes

    def test_service_lifetime_iteration(self) -> None:
        """Test iterating over service lifetimes."""
        lifetimes = [lt for lt in ServiceLifetime]
        assert len(lifetimes) == 3
        names = {lt.name for lt in lifetimes}
        assert names == {"SINGLETON", "TRANSIENT", "SCOPED"}
