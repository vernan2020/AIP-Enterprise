from __future__ import annotations

from collections.abc import Mapping

from aip.product.configured.irrbb.power_bi_msal_access_token_provider import (
    ConfiguredMSALPowerBIAccessTokenProvider,
    MSALPublicClientFactory,
    PowerBIAuthenticationProfileSource,
)
from aip.product.configured.irrbb.power_bi_semantic_metadata_fetcher import (
    ConfiguredPowerBISemanticMetadataSnapshotFetcher,
    PowerBIAccessTokenProvider,
    PowerBIHTTPTransport,
    UrllibPowerBIHTTPTransport,
)
from aip.product.configured.irrbb.power_bi_semantic_metadata_inspector import (
    ConfiguredPowerBISemanticModelMetadataInspector,
)
from aip.product.configured.irrbb.power_bi_semantic_route_resolver import (
    InstitutionalPowerBISemanticRouteResolver,
    PowerBISemanticRouteSettingsProvider,
)
from aip.product.configured.irrbb.semantic_model_inspection_coordinator import (
    GovernedSemanticModelInspectionCoordinator,
)


def build_configured_semantic_model_inspection_coordinator(
    *,
    settings_provider: PowerBISemanticRouteSettingsProvider,
    token_provider: PowerBIAccessTokenProvider,
    http_transport: PowerBIHTTPTransport | None = None,
    timeout_seconds: float = 30.0,
) -> GovernedSemanticModelInspectionCoordinator:
    """Compose metadata-only Power BI inspection with explicit auth injection."""

    route_resolver = InstitutionalPowerBISemanticRouteResolver(
        settings_provider=settings_provider,
    )
    snapshot_fetcher = ConfiguredPowerBISemanticMetadataSnapshotFetcher(
        token_provider=token_provider,
        http_transport=http_transport or UrllibPowerBIHTTPTransport(),
        timeout_seconds=timeout_seconds,
    )
    inspector = ConfiguredPowerBISemanticModelMetadataInspector(
        route_resolver=route_resolver,
        snapshot_fetcher=snapshot_fetcher,
    )
    return GovernedSemanticModelInspectionCoordinator(inspector=inspector)


def build_msal_semantic_model_inspection_coordinator(
    *,
    settings_provider: PowerBISemanticRouteSettingsProvider,
    authentication_profiles: Mapping[str, PowerBIAuthenticationProfileSource],
    client_factory: MSALPublicClientFactory | None = None,
    http_transport: PowerBIHTTPTransport | None = None,
    timeout_seconds: float = 30.0,
) -> GovernedSemanticModelInspectionCoordinator:
    """Compose the governed inspector with delegated MSAL public-client authentication."""

    token_provider = ConfiguredMSALPowerBIAccessTokenProvider(
        authentication_profiles,
        client_factory=client_factory,
    )
    return build_configured_semantic_model_inspection_coordinator(
        settings_provider=settings_provider,
        token_provider=token_provider,
        http_transport=http_transport,
        timeout_seconds=timeout_seconds,
    )
