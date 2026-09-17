from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceSegment,
)
from aip.application.irrbb.semantic_model_inspection import (
    IRRBBSemanticModelColumnMetadata,
    IRRBBSemanticModelInspectionSnapshot,
    IRRBBSemanticModelSchemaFreshness,
    IRRBBSemanticModelTableMetadata,
)
from aip.product.configured.irrbb.physical_source_registry import (
    BORROWING_WORKBOOK_SOURCE,
    CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.power_bi_semantic_metadata_inspector import (
    ConfiguredPowerBISemanticModelMetadataInspector,
)
from aip.product.configured.irrbb.power_bi_semantic_route import PowerBISemanticModelRoute
from aip.product.configured.irrbb.power_bi_semantic_route_resolver import (
    InstitutionalPowerBISemanticRouteResolver,
    PowerBISemanticRouteSettings,
)
from aip.product.configured.irrbb.semantic_model_inspection_coordinator import (
    GovernedSemanticModelInspectionCoordinator,
)

_CREDIT_DATASET_ID = "22345678-1234-4234-8234-1234567890ab"
_TERM_DATASET_ID = "32345678-1234-4234-8234-1234567890ab"
_WORKSPACE_ID = "12345678-1234-4234-8234-1234567890ab"
_AUTH_PROFILE = "security.auth.power_bi.readonly"


class _SettingsProvider:
    def __init__(self, settings_by_key: dict[str, PowerBISemanticRouteSettings]) -> None:
        self._settings_by_key = settings_by_key
        self.calls: list[str] = []

    def require(self, *, configuration_key: str) -> PowerBISemanticRouteSettings:
        self.calls.append(configuration_key)
        try:
            return self._settings_by_key[configuration_key]
        except KeyError as exc:
            raise KeyError(f"missing route settings for {configuration_key}") from exc


class _MetadataFetcher:
    def __init__(self, snapshot: IRRBBSemanticModelInspectionSnapshot) -> None:
        self._snapshot = snapshot
        self.calls: list[tuple[IRRBBPhysicalSourceDescriptor, PowerBISemanticModelRoute]] = []

    def fetch_metadata(
        self,
        *,
        source: IRRBBPhysicalSourceDescriptor,
        route: PowerBISemanticModelRoute,
    ) -> IRRBBSemanticModelInspectionSnapshot:
        self.calls.append((source, route))
        return self._snapshot


def _settings(
    *,
    dataset_id: str,
    workspace_id: str | None,
) -> PowerBISemanticRouteSettings:
    return PowerBISemanticRouteSettings(
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        authentication_profile_key=_AUTH_PROFILE,
    )


def _snapshot(
    *,
    source: IRRBBPhysicalSourceDescriptor = CREDIT_SEMANTIC_MODEL_SOURCE,
    source_id: str | None = None,
    logical_name: str | None = None,
) -> IRRBBSemanticModelInspectionSnapshot:
    return IRRBBSemanticModelInspectionSnapshot(
        source_id=source.source_id if source_id is None else source_id,
        logical_name=source.logical_name if logical_name is None else logical_name,
        provider_workspace_reference="runtime-workspace-reference",
        provider_model_reference="runtime-model-reference",
        provider_model_name=source.logical_name,
        inspection_method="provider-metadata-scan",
        observed_at=datetime(2026, 9, 17, 14, 30, tzinfo=UTC),
        schema_freshness=IRRBBSemanticModelSchemaFreshness.CURRENT,
        row_data_included=False,
        expressions_included=False,
        tables=(
            IRRBBSemanticModelTableMetadata(
                name="Operations",
                is_hidden=False,
                columns=(
                    IRRBBSemanticModelColumnMetadata(
                        name="OperationId",
                        data_type="String",
                        is_hidden=False,
                    ),
                ),
                measures=(),
            ),
        ),
        relationships=(),
    )


def test_resolver_builds_dataset_only_route_from_external_settings() -> None:
    provider = _SettingsProvider(
        {
            CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key: _settings(
                dataset_id=_CREDIT_DATASET_ID,
                workspace_id=None,
            )
        }
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)

    binding = resolver.resolve_segment(segment=IRRBBPhysicalSourceSegment.CREDIT)

    assert provider.calls == [CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key]
    assert binding.descriptor is CREDIT_SEMANTIC_MODEL_SOURCE
    assert str(binding.route.dataset_id) == _CREDIT_DATASET_ID
    assert binding.route.workspace_id is None
    assert binding.route.authentication_profile_key == _AUTH_PROFILE
    assert binding.route.execute_dax_queries_url.endswith(
        f"/datasets/{_CREDIT_DATASET_ID}/executeQueries"
    )


def test_resolver_preserves_explicit_workspace_route() -> None:
    provider = _SettingsProvider(
        {
            TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.configuration_key: _settings(
                dataset_id=_TERM_DATASET_ID,
                workspace_id=_WORKSPACE_ID,
            )
        }
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)

    binding = resolver.resolve_segment(segment=IRRBBPhysicalSourceSegment.TERM_DEPOSIT)

    assert binding.descriptor is TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE
    assert str(binding.route.workspace_id) == _WORKSPACE_ID
    assert str(binding.route.dataset_id) == _TERM_DATASET_ID
    assert f"/groups/{_WORKSPACE_ID}/datasets/" in binding.route.execute_dax_queries_url


def test_resolver_rejects_non_power_bi_segment_before_configuration_lookup() -> None:
    provider = _SettingsProvider({})
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)

    with pytest.raises(ValueError, match="semantic-model physical source"):
        resolver.resolve_source(source=BORROWING_WORKBOOK_SOURCE)

    assert provider.calls == []


def test_resolver_rejects_lookalike_source_before_configuration_lookup() -> None:
    forged = IRRBBPhysicalSourceDescriptor(
        source_id=CREDIT_SEMANTIC_MODEL_SOURCE.source_id,
        segment=IRRBBPhysicalSourceSegment.CREDIT,
        kind=IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL,
        logical_name="OtherCreditModel",
        configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        owner=CREDIT_SEMANTIC_MODEL_SOURCE.owner,
        location=CREDIT_SEMANTIC_MODEL_SOURCE.location,
    )
    provider = _SettingsProvider({})
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)

    with pytest.raises(ValueError, match="exact governed registered source"):
        resolver.resolve_source(source=forged)

    assert provider.calls == []


def test_resolver_fails_closed_when_external_dataset_id_is_invalid() -> None:
    provider = _SettingsProvider(
        {
            CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key: _settings(
                dataset_id="not-a-uuid",
                workspace_id=None,
            )
        }
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)

    with pytest.raises(ValueError, match="dataset_id.*canonical UUID"):
        resolver.resolve_segment(segment=IRRBBPhysicalSourceSegment.CREDIT)


def test_configured_metadata_inspector_resolves_route_and_returns_snapshot() -> None:
    provider = _SettingsProvider(
        {
            CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key: _settings(
                dataset_id=_CREDIT_DATASET_ID,
                workspace_id=None,
            )
        }
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)
    snapshot = _snapshot()
    fetcher = _MetadataFetcher(snapshot)
    inspector = ConfiguredPowerBISemanticModelMetadataInspector(
        route_resolver=resolver,
        snapshot_fetcher=fetcher,
    )

    result = inspector.inspect(source=CREDIT_SEMANTIC_MODEL_SOURCE)

    assert result == snapshot
    assert len(fetcher.calls) == 1
    source, route = fetcher.calls[0]
    assert source is CREDIT_SEMANTIC_MODEL_SOURCE
    assert str(route.dataset_id) == _CREDIT_DATASET_ID
    assert route.workspace_id is None


def test_configured_metadata_inspector_rejects_provider_source_substitution() -> None:
    provider = _SettingsProvider(
        {
            CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key: _settings(
                dataset_id=_CREDIT_DATASET_ID,
                workspace_id=None,
            )
        }
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)
    fetcher = _MetadataFetcher(_snapshot(source_id="other.source"))
    inspector = ConfiguredPowerBISemanticModelMetadataInspector(
        route_resolver=resolver,
        snapshot_fetcher=fetcher,
    )

    with pytest.raises(ValueError, match="different source_id"):
        inspector.inspect(source=CREDIT_SEMANTIC_MODEL_SOURCE)


def test_configured_metadata_inspector_integrates_with_governed_coordinator() -> None:
    provider = _SettingsProvider(
        {
            CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key: _settings(
                dataset_id=_CREDIT_DATASET_ID,
                workspace_id=None,
            )
        }
    )
    resolver = InstitutionalPowerBISemanticRouteResolver(settings_provider=provider)
    fetcher = _MetadataFetcher(_snapshot())
    inspector = ConfiguredPowerBISemanticModelMetadataInspector(
        route_resolver=resolver,
        snapshot_fetcher=fetcher,
    )
    coordinator = GovernedSemanticModelInspectionCoordinator(inspector=inspector)

    result = coordinator.inspect(segment=IRRBBPhysicalSourceSegment.CREDIT)

    assert result.source is CREDIT_SEMANTIC_MODEL_SOURCE
    assert result.snapshot == _snapshot()
    assert '"row_data_included": false' in result.evidence_document
    assert '"expressions_included": false' in result.evidence_document
