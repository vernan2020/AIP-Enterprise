from __future__ import annotations

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
    """Compose the metadata-only Power BI inspection path with explicit auth injection.

    The composition deliberately has no default credential acquisition strategy. The
    caller must provide an institutionally approved token provider. Only the stateless,
    Microsoft-host-pinned HTTP transport has a production default.
    """

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
