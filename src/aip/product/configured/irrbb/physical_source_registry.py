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


CREDIT_XML_CONFIA_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.credit.xml_confia.nec2024_5103",
    segment=IRRBBPhysicalSourceSegment.CREDIT,
    kind=IRRBBPhysicalSourceKind.XML_FILE,
    logical_name="NEC2024_Operaciones_5103.xml",
    configuration_key="irrbb.sources.xml_confia.credit",
    owner="Gerencia Financiera / Liquidez y Análisis Financiero",
    location="XML CONFÍA mensual",
)

CAPTACIONES_XML_CONFIA_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.liability.xml_confia.pasivos_210",
    segment=IRRBBPhysicalSourceSegment.CAPTACIONES,
    kind=IRRBBPhysicalSourceKind.XML_FILE,
    logical_name="Pasivos_Cuentas_Contables_210.xml",
    configuration_key="irrbb.sources.xml_confia.captaciones",
    owner="Gerencia Financiera / Liquidez y Análisis Financiero",
    location="XML CONFÍA mensual",
)

BORROWING_XML_CONFIA_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.liability.xml_confia.pasivos_220_230_260_270_280",
    segment=IRRBBPhysicalSourceSegment.BORROWING,
    kind=IRRBBPhysicalSourceKind.XML_FILE,
    logical_name="Pasivos_Cuentas_Contables_220_230_260_270_280.xml",
    configuration_key="irrbb.sources.xml_confia.borrowing",
    owner="Gerencia Financiera / Liquidez y Análisis Financiero",
    location="XML CONFÍA mensual",
)

INVESTMENT_XML_CONFIA_SOURCE = IRRBBPhysicalSourceDescriptor(
    source_id="coopealianza.investment.xml_confia.inversiones_activas",
    segment=IRRBBPhysicalSourceSegment.INVESTMENT,
    kind=IRRBBPhysicalSourceKind.XML_FILE,
    logical_name="Crediticio_InversionesActivas.xml",
    configuration_key="irrbb.sources.xml_confia.investment",
    owner="Gerencia Financiera / Liquidez y Análisis Financiero",
    location="XML CONFÍA mensual",
)

INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES = (
    CREDIT_XML_CONFIA_SOURCE,
    CAPTACIONES_XML_CONFIA_SOURCE,
    BORROWING_XML_CONFIA_SOURCE,
    INVESTMENT_XML_CONFIA_SOURCE,
)


def institutional_irrbb_physical_source_registry() -> IRRBBPhysicalSourceRegistry:
    """Build the governed institutional source registry without runtime source resolution."""

    return IRRBBPhysicalSourceRegistry(INSTITUTIONAL_IRRBB_PHYSICAL_SOURCES)
