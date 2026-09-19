from __future__ import annotations

from typing import Protocol

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceDescriptor
from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelInspectionSnapshot,
)
from aip.product.configured.irrbb.power_bi_semantic_route import PowerBISemanticModelRoute
from aip.product.configured.irrbb.power_bi_semantic_route_resolver import (
    InstitutionalPowerBISemanticRouteResolver,
)


class PowerBISemanticMetadataSnapshotFetcher(Protocol):
    """Provider boundary for metadata-only Power BI semantic-model inspection.

    Implementations own authentication and provider I/O. They must return the
    source-neutral metadata snapshot and must not return position rows, expressions,
    mapped IRRBB contracts or financial calculations.
    """

    def fetch_metadata(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
        route: PowerBISemanticModelRoute,
    ) -> IRRBBSemanticModelInspectionSnapshot: ...


class ConfiguredPowerBISemanticModelMetadataInspector:
    """Application-port adapter backed by governed Power BI runtime routing."""

    def __init__(
        self,
        *,
        route_resolver: InstitutionalPowerBISemanticRouteResolver,
        snapshot_fetcher: PowerBISemanticMetadataSnapshotFetcher,
    ) -> None:
        self._route_resolver = route_resolver
        self._snapshot_fetcher = snapshot_fetcher

    def inspect(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
    ) -> IRRBBSemanticModelInspectionSnapshot:
        """Resolve the governed route and fetch physical metadata only."""

        binding = self._route_resolver.resolve_source(source=source)
        snapshot = self._snapshot_fetcher.fetch_metadata(
            source=source,
            route=binding.route,
        )
        if snapshot.source_id != source.source_id:
            raise ValueError("Power BI metadata fetcher returned a different source_id")
        if snapshot.logical_name != source.logical_name:
            raise ValueError("Power BI metadata fetcher returned a different logical_name")
        return snapshot
