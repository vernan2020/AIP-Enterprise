from __future__ import annotations

from abc import ABC, abstractmethod


class CredentialValidator(ABC):
    """Abstract validator for credentials."""

    @abstractmethod
    def validate(self, username: str, password: str) -> bool:
        raise AssertionError("Subclasses must implement validate")


class StaticCredentialValidator(CredentialValidator):
    """Simple validator that compares against configured credentials."""

    def __init__(self, credentials: dict[str, str] | None = None) -> None:
        self._credentials = dict(credentials or {})

    def validate(self, username: str, password: str) -> bool:
        return self._credentials.get(username) == password
