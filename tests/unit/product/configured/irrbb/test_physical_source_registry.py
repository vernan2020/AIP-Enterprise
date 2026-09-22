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
    BORROWING_XML_CONFIA_SOURCE,
    CAPTACIONES_SEMANTIC_MODEL_SOURCE,
    CAPTACIONES_XML_CONFIA_SOURCE,
    CREDIT_SEMANTIC_MODEL_SOURCE,
    CREDIT_XML_CONFIA_SOURCE,
    INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES,
    INVESTMENT_PORTFOLIO_SOURCE,
    INVESTMENT_XML_CONFIA_SOURCE,
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


def test_xml_confia_sources_are_primary_for_all_four_irrbb_segments() -> None:
    expected = (
        CREDIT_XML_CONFIA_SOURCE,
        CAPTACIONES_XML_CONFIA_SOURCE,
        BORROWING_XML_CONFIA_SOURCE,
        INVESTMENT_XML_CONFIA_SOURCE,
    )

    assert INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES == expected
    assert all(source.kind is IRRBBPhysicalSourceKind.XML_DOCUMENT for source in expected)
    assert CREDIT_XML_CONFIA_SOURCE.logical_name == "NEC2024_Operaciones_5103.xml"
    assert CAPTACIONES_XML_CONFIA_SOURCE.logical_name == "Pasivos_Cuentas_Contables_210.xml"
    assert BORROWING_XML_CONFIA_SOURCE.logical_name == (
        "Pasivos_Cuentas_Contables_220_230_260_270_280.xml"
    )
    assert INVESTMENT_XML_CONFIA_SOURCE.logical_name == "Crediticio_InversionesActivas.xml"
    assert all(source.location == "XML CONFÍA / corte mensual" for source in expected)


def test_power_bi_semantic_model_identities_remain_governed_as_historical_candidates() -> None:
    assert CREDIT_SEMANTIC_MODEL_SOURCE.logical_name == "Credito"
    assert CREDIT_SEMANTIC_MODEL_SOURCE.owner == "TIPowerBI"
    assert CREDIT_SEMANTIC_MODEL_SOURCE.location == "MS Área de Crédito"
    assert CREDIT_SEMANTIC_MODEL_SOURCE.kind is IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL

    assert CAPTACIONES_SEMANTIC_MODEL_SOURCE.logical_name == "Captaciones"
    assert CAPTACIONES_SEMANTIC_MODEL_SOURCE.owner == "TIPowerBI"
    assert CAPTACIONES_SEMANTIC_MODEL_SOURCE.location == "MS Área de Ahorros"
    assert CAPTACIONES_SEMANTIC_MODEL_SOURCE.kind is IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL
    assert CAPTACIONES_SEMANTIC_MODEL_SOURCE.segment is IRRBBPhysicalSourceSegment.CAPTACIONES
    assert "term_deposit" not in CAPTACIONES_SEMANTIC_MODEL_SOURCE.configuration_key
    assert "certificados" not in CAPTACIONES_SEMANTIC_MODEL_SOURCE.source_id


def test_historical_borrowing_workbook_keeps_configuration_key_not_personal_path() -> None:
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


def test_historical_investment_portfolio_source_identity_is_retained() -> None:
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
        IRRBBPhysicalSourceSegment.CAPTACIONES.certification_perimeter
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

    assert registry.require(IRRBBPhysicalSourceSegment.CREDIT) is CREDIT_XML_CONFIA_SOURCE
    assert registry.require(IRRBBPhysicalSourceSegment.CAPTACIONES) is CAPTACIONES_XML_CONFIA_SOURCE
    assert registry.require(IRRBBPhysicalSourceSegment.BORROWING) is BORROWING_XML_CONFIA_SOURCE
    assert registry.require(IRRBBPhysicalSourceSegment.INVESTMENT) is INVESTMENT_XML_CONFIA_SOURCE
