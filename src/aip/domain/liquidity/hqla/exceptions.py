from __future__ import annotations


class HQLAError(Exception):
    """Raised for invalid or unsupported HQLA operations."""


class HQLAProviderError(HQLAError):
    """Raised when an HQLA provider fails."""
