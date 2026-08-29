from __future__ import annotations

from abc import ABC, abstractmethod

from aip.platform.security.identity.identity import Identity


class IdentityProvider(ABC):
    """Abstract provider for resolving identities."""

    @abstractmethod
    def get_identity(self, subject: str) -> Identity:
        raise AssertionError("Subclasses must implement get_identity")


class InMemoryIdentityProvider(IdentityProvider):
    """Simple in-memory identity provider for tests and local usage."""

    def __init__(self, identities: dict[str, Identity] | None = None) -> None:
        self._identities = dict(identities or {})

    def register(self, identity: Identity) -> None:
        self._identities[identity.subject] = identity

    def get_identity(self, subject: str) -> Identity:
        if subject not in self._identities:
            raise KeyError(f"Identity not found: {subject}")
        return self._identities[subject]
