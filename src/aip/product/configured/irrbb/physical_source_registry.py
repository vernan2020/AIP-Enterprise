from __future__ import annotations

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceRegistry,
    IRRBBPhysicalSourceSegment,
)

CREDIT_SEMANTIC_MODEL_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.credit.powerbi.credito",
    segment=IRRBBPhysicalSourceSegment.CREDIT,
    kind=IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL,
    logical_name="Credito",
    configuration_key="irrbb.sources.credit.power_bi",
    owner="TIPowerBI",
    location="MS Área de Crédito",
)

CAPTACIONES_SEMANTIC_MODEL_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.liability.powerbi.captaciones",
    segment=IRRBBPhysicalSourceSegment.CAPTACIONES,
    kind=IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL,
    logical_name="Captaciones",
    configuration_key="irrbb.sources.captaciones.power_bi",
    owner="TIPowerBI",
    location="MS Área de Ahorros",
)

BORROWING_WORKBOOK_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.liability.excel.obligaciones_entidades",
    segment=IRRBBPhysicalSourceSegment.BORROWING,
    kind=IRRBBPhysicalSourceKind.EXCEL_WORKBOOK,
    logical_name="Auxiliar Obligaciones Entidades 2026.xlsx",
    configuration_key="irrbb.sources.borrowing.workbook",
)

INVESTMENT_PORTFOLIO_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.investment.portfolio_master",
    segment=IRRBBPhysicalSourceSegment.INVESTMENT,
    kind=IRRBBPhysicalSourceKind.PORTFOLIO_MASTER,
    logical_name="Portafolio de Inversiones",
    configuration_key="irrbb.sources.investment.portfolio_master",
)

INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES = (
    CREDIT_SEMANTIC_MODEL_SOURCE,
    CAPTACIONES_SEMANTIC_MODEL_SOURCE,
    BORROWING_WORKBOOK_SOURCE,
    INVESTMENT_PORTFOLIO_SOURCE,
)


def institutional_irrbb_physical_source_registry() -> IRRBBPhysicalSourceRegistry:
    """Build the governed institutional source registry without runtime source resolution."""

    return IRRBBPhysicalSourceRegistry(INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES)
