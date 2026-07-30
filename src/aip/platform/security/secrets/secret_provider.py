from __future__ import annotations

from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """Abstract provider for secrets."""

    @abstractmethod
    def get_secret(self, name: str) -> str:
        raise AssertionError("Subclasses must implement get_secret")


class InMemorySecretProvider(SecretProvider):
    """In-memory provider for test and local environments."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})

    def register(self, name: str, value: str) -> None:
        self._secrets[name] = value

    def get_secret(self, name: str) -> str:
        return self._secrets[name]


class EnvironmentSecretProvider(SecretProvider):
    """Environment-variable backed provider."""

    def __init__(self, prefix: str | None = None) -> None:
        self._prefix = prefix

    def get_secret(self, name: str) -> str:
        import os

        full_name = f"{self._prefix}{name}" if self._prefix else name
        value = os.getenv(full_name)
        if value is None:
            raise KeyError(f"Secret not found: {full_name}")
        return value
