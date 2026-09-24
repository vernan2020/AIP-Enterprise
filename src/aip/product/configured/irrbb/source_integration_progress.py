from __future__ import annotations

from dataclasses import dataclass

from aip.application.irrbb.physical_source_registry import IRRBBPhysicalSourceSegment
from aip.product.configured.irrbb.physical_source_registry import (
    BORROWING_XML_CONFIA_SOURCE,
    CAPTACIONES_XML_CONFIA_SOURCE,
    CREDIT_XML_CONFIA_SOURCE,
    INVESTMENT_PORTFOLIO_SOURCE,
)


@dataclass(frozen=True, slots=True)
class IRRBBSourceIntegrationProgress:
    """Truthful, non-financial progress metadata consumed by the passive UI."""

    segment: IRRBBPhysicalSourceSegment
    primary_source: str
    technology: str
    contractual_complement: str
    normalization_status: str
    bucket_status: str
    gap_status: str
    eve_status: str
    pending_gate: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("primary_source", self.primary_source),
            ("technology", self.technology),
            ("contractual_complement", self.contractual_complement),
            ("normalization_status", self.normalization_status),
            ("bucket_status", self.bucket_status),
            ("gap_status", self.gap_status),
            ("eve_status", self.eve_status),
            ("pending_gate", self.pending_gate),
        ):
            if not value.strip():
                raise ValueError(f"source integration {field_name} is required")


INSTITUTIONAL_IRRBB_SOURCE_PROGRESS = (
    IRRBBSourceIntegrationProgress(
        segment=IRRBBPhysicalSourceSegment.CREDIT,
        primary_source=CREDIT_XML_CONFIA_SOURCE.logical_name,
        technology=CREDIT_XML_CONFIA_SOURCE.kind.value,
        contractual_complement="No certificado",
        normalization_status="AUDITADA",
        bucket_status="19 BANDAS · TEMPORAL",
        gap_status="PENDIENTE CANÓNICO",
        eve_status="BLOQUEADO",
        pending_gate="Moneda aprobada, posición canónica y cash flows contractuales.",
    ),
    IRRBBSourceIntegrationProgress(
        segment=IRRBBPhysicalSourceSegment.CAPTACIONES,
        primary_source=CAPTACIONES_XML_CONFIA_SOURCE.logical_name,
        technology=CAPTACIONES_XML_CONFIA_SOURCE.kind.value,
        contractual_complement="CAPF XLSX contractual",
        normalization_status="XML + CAPF AUDITADOS",
        bucket_status="CAPF PRINCIPAL · 19 BANDAS",
        gap_status="COMPONENTE PARCIAL",
        eve_status="BLOQUEADO",
        pending_gate=(
            "Cupones/capitalización contractuales, NMD aprobado y fila GAP institucional."
        ),
    ),
    IRRBBSourceIntegrationProgress(
        segment=IRRBBPhysicalSourceSegment.BORROWING,
        primary_source=BORROWING_XML_CONFIA_SOURCE.logical_name,
        technology=BORROWING_XML_CONFIA_SOURCE.kind.value,
        contractual_complement="Tabla vencimientos + XLSX obligaciones",
        normalization_status="XML AUDITADO",
        bucket_status="PENDIENTE",
        gap_status="PENDIENTE",
        eve_status="BLOQUEADO",
        pending_gate="Llave contractual, primera cuota, frecuencia y principal reconciliado.",
    ),
    IRRBBSourceIntegrationProgress(
        segment=IRRBBPhysicalSourceSegment.INVESTMENT,
        primary_source=INVESTMENT_PORTFOLIO_SOURCE.logical_name,
        technology=INVESTMENT_PORTFOLIO_SOURCE.kind.value,
        contractual_complement="No aplica",
        normalization_status="GATE FAIL-CLOSED",
        bucket_status="PENDIENTE",
        gap_status="PENDIENTE",
        eve_status="BLOQUEADO",
        pending_gate="Política certificada, repricing y cash flows contractuales.",
    ),
)
