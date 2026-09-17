from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from aip.product.configured.irrbb.power_bi_semantic_route_resolver import (
    PowerBISemanticRouteSettings,
)


class PowerBISemanticRouteConfiguration(Protocol):
    """Structural configuration required to build one governed runtime route."""

    dataset_id: str
    workspace_id: str | None
    authentication_profile_key: str


class ConfiguredPowerBISemanticRouteSettingsProvider:
    """Immutable snapshot of deployment-owned Power BI route configuration.

    The provider performs no file, environment, network or authentication access.
    It receives already-loaded non-secret configuration from the composition root
    and fails closed when a governed configuration key is absent.
    """

    def __init__(
        self,
        settings_by_key: Mapping[str, PowerBISemanticRouteConfiguration],
    ) -> None:
        snapshot: dict[str, PowerBISemanticRouteSettings] = {}
        for configuration_key, configuration in settings_by_key.items():
            self._validate_configuration_key(configuration_key)
            snapshot[configuration_key] = PowerBISemanticRouteSettings(
                dataset_id=configuration.dataset_id,
                workspace_id=configuration.workspace_id,
                authentication_profile_key=configuration.authentication_profile_key,
            )
        self._settings_by_key = snapshot

    def require(
        self,
        *,
        configuration_key: str,
    ) -> PowerBISemanticRouteSettings:
        self._validate_configuration_key(configuration_key)
        try:
            return self._settings_by_key[configuration_key]
        except KeyError as exc:
            raise KeyError(
                f"No Power BI semantic route settings configured for {configuration_key!r}"
            ) from exc

    @staticmethod
    def _validate_configuration_key(configuration_key: str) -> None:
        if not configuration_key or configuration_key != configuration_key.strip():
            raise ValueError("Power BI semantic route configuration key must be non-blank")
