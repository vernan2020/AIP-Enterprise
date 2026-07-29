from __future__ import annotations

from aip.platform.notifications.providers.provider import Provider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        self._providers[provider.name] = provider

    def unregister(self, provider_name: str) -> bool:
        if provider_name in self._providers:
            del self._providers[provider_name]
            return True
        return False

    def lookup(self, provider_name: str) -> Provider | None:
        return self._providers.get(provider_name)

    def health(self, provider_name: str) -> bool:
        provider = self.lookup(provider_name)
        return bool(provider is not None and provider.health())
