from __future__ import annotations

from uuid import UUID

import pytest

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceSegment,
)
from aip.product.configured.irrbb.physical_source_registry import (
    BORROWING_WORKBOOK_SOURCE,
    CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)
from aip.product.configured.irrbb.power_bi_semantic_route import (
    InstitutionalPowerBISemanticRouteBinding,
    PowerBISemanticModelRoute,
    PowerBISemanticQueryTransport,
)

_WORKSPACE_ID = "12345678-1234-4234-8234-1234567890ab"
_CREDIT_DATASET_ID = "22345678-1234-4234-8234-1234567890ab"
_TERM_DATASET_ID = "32345678-1234-4234-8234-1234567890ab"


def _route(
    *,
    configuration_key: str,
    dataset_id: str = _CREDIT_DATASET_ID,
) -> PowerBISemanticModelRoute:
    return PowerBISemanticModelRoute.from_strings(
        configuration_key=configuration_key,
        workspace_id=_WORKSPACE_ID,
        dataset_id=dataset_id,
        authentication_profile_key="security.auth.power_bi.readonly",
    )


def test_credit_and_term_deposit_routes_bind_to_exact_governed_sources() -> None:
    credit_route = _route(configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key)
    term_route = _route(
        configuration_key=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        dataset_id=_TERM_DATASET_ID,
    )

    credit_binding = InstitutionalPowerBISemanticRouteBinding(
        descriptor=CREDIT_SEMANTIC_MODEL_SOURCE,
        route=credit_route,
    )
    term_binding = InstitutionalPowerBISemanticRouteBinding(
        descriptor=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
        route=term_route,
    )

    assert credit_binding.descriptor.segment is IRRBBPhysicalSourceSegment.CREDIT
    assert term_binding.descriptor.segment is IRRBBPhysicalSourceSegment.TERM_DEPOSIT
    assert credit_binding.source_reference.startswith(
        f"{CREDIT_SEMANTIC_MODEL_SOURCE.source_id}@powerbi://workspace/"
    )
    assert term_binding.source_reference.startswith(
        f"{TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.source_id}@powerbi://workspace/"
    )


def test_execute_dax_endpoint_is_pinned_to_microsoft_host() -> None:
    route = _route(configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key)

    assert route.execute_dax_queries_url == (
        "https://api.powerbi.com/v1.0/myorg/groups/"
        f"{_WORKSPACE_ID}/datasets/{_CREDIT_DATASET_ID}/executeDaxQueries"
    )
    assert "security.auth.power_bi.readonly" not in route.execute_dax_queries_url
    assert "security.auth.power_bi.readonly" not in route.safe_reference


def test_route_uses_only_approved_arrow_transport() -> None:
    route = _route(configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key)
    assert route.transport is PowerBISemanticQueryTransport.EXECUTE_DAX_QUERIES_ARROW

    with pytest.raises(ValueError, match="unsupported Power BI semantic query transport"):
        PowerBISemanticModelRoute(
            configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
            workspace_id=UUID(_WORKSPACE_ID),
            dataset_id=UUID(_CREDIT_DATASET_ID),
            authentication_profile_key="security.auth.power_bi.readonly",
            transport="OTHER",  # type: ignore[arg-type]
        )


def test_non_power_bi_and_configuration_mismatch_fail_closed() -> None:
    route = _route(configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key)

    with pytest.raises(ValueError, match="semantic-model physical source"):
        InstitutionalPowerBISemanticRouteBinding(
            descriptor=BORROWING_WORKBOOK_SOURCE,
            route=route,
        )

    wrong_key_route = _route(
        configuration_key=TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.configuration_key
    )
    with pytest.raises(ValueError, match="configuration_key"):
        InstitutionalPowerBISemanticRouteBinding(
            descriptor=CREDIT_SEMANTIC_MODEL_SOURCE,
            route=wrong_key_route,
        )


def test_lookalike_descriptor_is_rejected_even_if_kind_and_segment_match() -> None:
    forged = IRRBBPhysicalSourceDescriptor(
        source_id=CREDIT_SEMANTIC_MODEL_SOURCE.source_id,
        segment=IRRBBPhysicalSourceSegment.CREDIT,
        kind=IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL,
        logical_name="Different model",
        configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        owner=CREDIT_SEMANTIC_MODEL_SOURCE.owner,
        location=CREDIT_SEMANTIC_MODEL_SOURCE.location,
    )
    route = _route(configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key)

    with pytest.raises(ValueError, match="exact governed institutional source"):
        InstitutionalPowerBISemanticRouteBinding(descriptor=forged, route=route)


def test_uuid_inputs_are_canonical_non_nil_identifiers() -> None:
    kwargs = {
        "configuration_key": CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        "workspace_id": _WORKSPACE_ID,
        "dataset_id": _CREDIT_DATASET_ID,
        "authentication_profile_key": "security.auth.power_bi.readonly",
    }

    with pytest.raises(ValueError, match="workspace_id.*canonical UUID"):
        PowerBISemanticModelRoute.from_strings(**{**kwargs, "workspace_id": "not-a-uuid"})
    with pytest.raises(ValueError, match="dataset_id.*nil UUID"):
        PowerBISemanticModelRoute.from_strings(
            **{**kwargs, "dataset_id": "00000000-0000-0000-0000-000000000000"}
        )
    with pytest.raises(ValueError, match="dataset_id.*canonical UUID"):
        PowerBISemanticModelRoute.from_strings(
            **{**kwargs, "dataset_id": "323456781234423482341234567890ab"}
        )


def test_configuration_and_authentication_references_are_opaque_keys() -> None:
    with pytest.raises(ValueError, match="configuration_key.*opaque"):
        PowerBISemanticModelRoute.from_strings(
            configuration_key="https://evil.example/route",
            workspace_id=_WORKSPACE_ID,
            dataset_id=_CREDIT_DATASET_ID,
            authentication_profile_key="security.auth.power_bi.readonly",
        )

    with pytest.raises(ValueError, match="authentication_profile_key.*opaque"):
        PowerBISemanticModelRoute.from_strings(
            configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
            workspace_id=_WORKSPACE_ID,
            dataset_id=_CREDIT_DATASET_ID,
            authentication_profile_key=" bearer secret ",
        )


def test_direct_constructor_rejects_non_uuid_runtime_values() -> None:
    with pytest.raises(ValueError, match="workspace_id.*must be a UUID"):
        PowerBISemanticModelRoute(
            configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
            workspace_id=_WORKSPACE_ID,  # type: ignore[arg-type]
            dataset_id=UUID(_CREDIT_DATASET_ID),
            authentication_profile_key="security.auth.power_bi.readonly",
        )
