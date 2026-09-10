from __future__ import annotations

import pytest

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceRegistry,
    IRRBBPhysicalSourceSegment,
)
from aip.application.irrbb.source_certification import IRRBBSourcePerimeter
from aip.product.configured.irrbb.physical_source_registry import (
    BORROWING_WORKBOOK_SOURCE,
    CREDIT_SEMANTIC_MODEL_SOURCE,
    INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES,
    INVESTMENT_PORTFOLIO_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
    institutional_irrbb_physical_source_registry,
)


def _source(
    *,
    source_id: str = "test.source",
    segment: IRRBBPhysicalSourceSegment = IRRBBPhysicalSourceSegment.CREDIT,
    configuration_key: str = "test.source.config",
) -> IRRBBPhysicalSourceDescriptor:
    return IRRBBPhysicalSourceDescriptor(
        source_id=source_id,
        segment=segment,
        kind=IRRBBPhysicalSourceKind.EXCEL_WORKBOOK,
        logical_name="Test source",
        configuration_key=configuration_key,
    )


def test_institutional_registry_has_exactly_one_source_for_each_position_segment() -> None:
    registry = institutional_irrbb_physical_source_registry()

    assert registry.sources == INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES
    assert {item.segment for item in registry.sources} == set(IRRBBPhysicalSourceSegment)
    assert len(registry.sources) == 4


def test_power_bi_semantic_model_identities_are_governed_without_schema_assumptions() -> None:
    assert CREDIT_SEMANTIC_MODEL_SOURCE.logical_name == "Credito"
    assert CREDIT_SEMANTIC_MODEL_SOURCE.owner == "TIPowerBI"
    assert CREDIT_SEMANTIC_MODEL_SOURCE.location == "MS Área de Crédito"
    assert CREDIT_SEMANTIC_MODEL_SOURCE.kind is IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL

    assert TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.logical_name == "Certificados"
    assert TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.owner == "TIPowerBI"
    assert TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.location == "MS Área de Ahorros"
    assert (
        TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE.kind is IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL
    )


def test_borrowing_registry_uses_configuration_key_not_personal_workstation_path() -> None:
    assert BORROWING_WORKBOOK_SOURCE.logical_name == "Auxiliar Obligaciones Entidades 2026.xlsx"
    assert BORROWING_WORKBOOK_SOURCE.kind is IRRBBPhysicalSourceKind.EXCEL_WORKBOOK
    assert BORROWING_WORKBOOK_SOURCE.configuration_key == "irrbb.sources.borrowing.workbook"

    serialized = "|".join(
        (
            BORROWING_WORKBOOK_SOURCE.source_id,
            BORROWING_WORKBOOK_SOURCE.logical_name,
            BORROWING_WORKBOOK_SOURCE.configuration_key,
            BORROWING_WORKBOOK_SOURCE.owner or "",
            BORROWING_WORKBOOK_SOURCE.location or "",
        )
    )
    assert "C:\\Users\\" not in serialized
    assert "ahidalgo" not in serialized.casefold()


def test_investments_continue_to_use_portfolio_master_source_identity() -> None:
    assert INVESTMENT_PORTFOLIO_SOURCE.logical_name == "Portafolio de Inversiones"
    assert INVESTMENT_PORTFOLIO_SOURCE.kind is IRRBBPhysicalSourceKind.PORTFOLIO_MASTER
    assert INVESTMENT_PORTFOLIO_SOURCE.segment is IRRBBPhysicalSourceSegment.INVESTMENT


def test_registry_does_not_register_aggregate_icl_or_unproven_sql_view_as_contractual_source() -> (
    None
):
    serialized = "|".join(
        f"{item.source_id}|{item.logical_name}|{item.configuration_key}"
        for item in INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES
    ).casefold()

    assert "icl" not in serialized
    assert "vista_1514_1515_1516" not in serialized


def test_physical_segments_map_to_existing_source_certification_perimeters() -> None:
    assert IRRBBPhysicalSourceSegment.CREDIT.certification_perimeter is IRRBBSourcePerimeter.CREDIT
    assert (
        IRRBBPhysicalSourceSegment.TERM_DEPOSIT.certification_perimeter
        is IRRBBSourcePerimeter.LIABILITY
    )
    assert (
        IRRBBPhysicalSourceSegment.BORROWING.certification_perimeter
        is IRRBBSourcePerimeter.LIABILITY
    )
    assert (
        IRRBBPhysicalSourceSegment.INVESTMENT.certification_perimeter
        is IRRBBSourcePerimeter.INVESTMENT
    )


def test_registry_rejects_duplicate_source_ids_segments_and_configuration_keys() -> None:
    with pytest.raises(ValueError, match="source_id values must be unique"):
        IRRBBPhysicalSourceRegistry(
            (
                _source(),
                _source(
                    segment=IRRBBPhysicalSourceSegment.INVESTMENT,
                    configuration_key="test.other.config",
                ),
            )
        )

    with pytest.raises(ValueError, match="segments must be unique"):
        IRRBBPhysicalSourceRegistry(
            (
                _source(),
                _source(source_id="test.other", configuration_key="test.other.config"),
            )
        )

    with pytest.raises(ValueError, match="configuration_key values must be unique"):
        IRRBBPhysicalSourceRegistry(
            (
                _source(),
                _source(
                    source_id="test.other",
                    segment=IRRBBPhysicalSourceSegment.INVESTMENT,
                ),
            )
        )


def test_descriptor_rejects_blank_required_and_optional_metadata() -> None:
    with pytest.raises(ValueError, match="source_id is required"):
        _source(source_id=" ")

    with pytest.raises(ValueError, match="configuration_key is required"):
        _source(configuration_key=" ")

    with pytest.raises(ValueError, match="owner cannot be blank"):
        IRRBBPhysicalSourceDescriptor(
            source_id="test.source",
            segment=IRRBBPhysicalSourceSegment.CREDIT,
            kind=IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL,
            logical_name="Test",
            configuration_key="test.config",
            owner=" ",
        )


def test_registry_missing_segment_fails_instead_of_falling_back() -> None:
    registry = IRRBBPhysicalSourceRegistry((_source(),))

    with pytest.raises(
        KeyError, match="no physical IRRBB source registered for segment INVESTMENT"
    ):
        registry.require(IRRBBPhysicalSourceSegment.INVESTMENT)


def test_registry_lookup_returns_exact_registered_descriptor() -> None:
    registry = institutional_irrbb_physical_source_registry()

    assert registry.require(IRRBBPhysicalSourceSegment.CREDIT) is CREDIT_SEMANTIC_MODEL_SOURCE
    assert (
        registry.require(IRRBBPhysicalSourceSegment.TERM_DEPOSIT)
        is TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE
    )
    assert registry.require(IRRBBPhysicalSourceSegment.BORROWING) is BORROWING_WORKBOOK_SOURCE
    assert registry.require(IRRBBPhysicalSourceSegment.INVESTMENT) is INVESTMENT_PORTFOLIO_SOURCE
