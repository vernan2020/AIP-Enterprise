from __future__ import annotations

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceSegment
from aip.product.configured.irrbb.source_integration_progress import (
    INSTITUTIONAL_IRRBB_SOURCE_PROGRESS,
)


def test_progress_distinguishes_partial_gap_components_from_eve_readiness() -> None:
    rows = {item.segment: item for item in INSTITUTIONAL_IRRBB_SOURCE_PROGRESS}

    assert set(rows) == set(IRRBBPhysicalSourceSegment)
    capf = rows[IRRBBPhysicalSourceSegment.CAPTACIONES]
    assert capf.primary_source == "Pasivos_Cuentas_Contables_210.xml"
    assert capf.contractual_complement == "CAPF XLSX contractual"
    assert capf.bucket_status == "CAPF PRINCIPAL · 19 BANDAS"
    assert capf.gap_status == "COMPONENTE PARCIAL"
    assert capf.eve_status == "BLOQUEADO"
    assert "Cupones/capitalización" in capf.pending_gate


def test_progress_keeps_investment_master_as_primary_source() -> None:
    investment = next(
        item
        for item in INSTITUTIONAL_IRRBB_SOURCE_PROGRESS
        if item.segment is IRRBBPhysicalSourceSegment.INVESTMENT
    )

    assert investment.primary_source == "Maestro de Inversiones - cierre mensual"
    assert investment.technology == "PORTFOLIO_MASTER"
    assert investment.bucket_status == "PENDIENTE"
    assert investment.eve_status == "BLOQUEADO"
