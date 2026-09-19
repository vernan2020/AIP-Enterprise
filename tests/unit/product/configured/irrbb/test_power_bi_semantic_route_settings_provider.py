from __future__ import annotations

import pytest
from pydantic import ValidationError

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceSegment
from aip.infrastructure.configuration.models import (
    PowerBISemanticRouteConfiguration,
    Settings,
)
from aip.product.configured.irrbb.physical_source_registry import (
    CREDIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.power_bi_semantic_route_resolver import (
    InstitutionalPowerBISemanticRouteResolver,
)
from aip.product.configured.irrbb.power_bi_semantic_route_settings_provider import (
    ConfiguredPowerBISemanticRouteSettingsProvider,
)

_DATASET_ID = "22345678-1234-4234-8234-1234567890ab"
_OTHER_DATASET_ID = "32345678-1234-4234-8234-1234567890ab"
_WORKSPACE_ID = "12345678-1234-4234-8234-1234567890ab"
_AUTH_PROFILE = "security.auth.power_bi.readonly"


def _configuration(
    *,
    dataset_id: str = _DATASET_ID,
    workspace_id: str | None = None,
) -> PowerBISemanticRouteConfiguration:
    return PowerBISemanticRouteConfiguration(
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        authentication_profile_key=_AUTH_PROFILE,
    )


def test_settings_default_to_no_power_bi_semantic_routes() -> None:
    settings = Settings()

    assert settings.irrbb.power_bi_semantic_routes == {}


def test_route_configuration_contains_no_authentication_material_field() -> None:
    assert set(PowerBISemanticRouteConfiguration.model_fields) == {
        "dataset_id",
        "workspace_id",
        "authentication_profile_key",
    }


def test_route_configuration_rejects_blank_non_secret_references() -> None:
    with pytest.raises(ValidationError):
        PowerBISemanticRouteConfiguration(
            dataset_id="   ",
            workspace_id=None,
            authentication_profile_key=_AUTH_PROFILE,
        )

    with pytest.raises(ValidationError):
        PowerBISemanticRouteConfiguration(
            dataset_id=_DATASET_ID,
            workspace_id=None,
            authentication_profile_key="   ",
        )


def test_provider_snapshots_external_mapping() -> None:
    configuration_key = CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key
    routes = {configuration_key: _configuration()}
    provider = ConfiguredPowerBISemanticRouteSettingsProvider(routes)

    routes[configuration_key] = _configuration(dataset_id=_OTHER_DATASET_ID)

    resolved = provider.require(configuration_key=configuration_key)
    assert resolved.dataset_id == _DATASET_ID


def test_provider_fails_closed_when_route_is_not_configured() -> None:
    provider = ConfiguredPowerBISemanticRouteSettingsProvider({})

    with pytest.raises(KeyError, match="No Power BI semantic route settings configured"):
        provider.require(configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key)


def test_provider_rejects_noncanonical_configuration_key() -> None:
    with pytest.raises(ValueError, match="configuration key must be non-blank"):
        ConfiguredPowerBISemanticRouteSettingsProvider(
            {" irrbb.sources.credit.power_bi ": _configuration()}
        )


def test_central_settings_flow_into_governed_runtime_resolver() -> None:
    configuration_key = CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key
    settings = Settings.model_validate(
        {
            "irrbb": {
                "power_bi_semantic_routes": {
                    configuration_key: {
                        "dataset_id": _DATASET_ID,
                        "workspace_id": _WORKSPACE_ID,
                        "authentication_profile_key": _AUTH_PROFILE,
                    }
                }
            }
        }
    )
    provider = ConfiguredPowerBISemanticRouteSettingsProvider(
        settings.irrbb.power_bi_semantic_routes
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)

    binding = resolver.resolve_segment(segment=IRRBBPhysicalSourceSegment.CREDIT)

    assert binding.descriptor is CREDIT_SEMANTIC_MODEL_SOURCE
    assert str(binding.route.dataset_id) == _DATASET_ID
    assert str(binding.route.workspace_id) == _WORKSPACE_ID
    assert binding.route.authentication_profile_key == _AUTH_PROFILE
