from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceRegistry,
    IRRBBPhysicalSourceSegment,
)
from aip.product.configured.irrbb.physical_source_registry import (
    historical_irrbb_candidate_source_registry,
)
from aip.product.configured.irrbb.power_bi_semantic_route import (
    InstitutionalPowerBISemanticRouteBinding,
    PowerBISemanticModelRoute,
)


@dataclass(frozen=True, slots=True)
class PowerBISemanticRouteSettings:
    """Deployment-owned, non-secret settings for one Power BI semantic route.

    Dataset/workspace identifiers are supplied by deployment configuration and are
    intentionally absent from the governed source registry. Authentication material
    is not accepted here; only an opaque authentication-profile reference is allowed.
    """

    dataset_id: str
    workspace_id: str | None
    authentication_profile_key: str


class PowerBISemanticRouteSettingsProvider(Protocol):
    """Port for resolving deployment-owned Power BI route settings."""

    def require(
        self,
        *,
        configuration_key: str,
    ) -> PowerBISemanticRouteSettings: ...


class InstitutionalPowerBISemanticRouteResolver:
    """Resolve exact governed semantic sources to validated runtime routes.

    The resolver is fail-closed: it accepts only a source registered in the
    retained institutional candidate-source registry, requires Power BI source kind,
    and delegates UUID/reference validation to ``PowerBISemanticModelRoute``.
    """

    def __init__(
        self,
        *,
        settings_provider: PowerBISemanticRouteSettingsProvider,
        registry: IRRBBPhysicalSourceRegistry | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._registry = (
            registry if registry is not None else historical_irrbb_candidate_source_registry()
        )

    def resolve_segment(
        self,
        *,
        segment: IRRBBPhysicalSourceSegment,
    ) -> InstitutionalPowerBISemanticRouteBinding:
        """Resolve the governed source registered for one semantic-model segment."""

        source = self._registry.require(segment)
        return self.resolve_source(source=source)

    def resolve_source(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
    ) -> InstitutionalPowerBISemanticRouteBinding:
        """Resolve one exact governed source without allowing lookalike substitution."""

        registered_source = self._registry.require(source.segment)
        if source != registered_source:
            raise ValueError("Power BI route source is not the exact governed registered source")
        if source.kind is not IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL:
            raise ValueError("Power BI route requires a semantic-model physical source")

        settings = self._settings_provider.require(
            configuration_key=source.configuration_key,
        )
        route = PowerBISemanticModelRoute.from_strings(
            configuration_key=source.configuration_key,
            workspace_id=settings.workspace_id,
            dataset_id=settings.dataset_id,
            authentication_profile_key=settings.authentication_profile_key,
        )
        return InstitutionalPowerBISemanticRouteBinding(
            descriptor=source,
            route=route,
        )
