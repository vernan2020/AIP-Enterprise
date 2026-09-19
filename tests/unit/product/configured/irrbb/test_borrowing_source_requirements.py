from __future__ import annotations

from aip.application.irrbb.source_certification import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationStatus,
)
from aip.product.configured.irrbb.borrowing_inspection_evidence import (
    BorrowingInspectionEvidenceBundle,
    ValidatedBorrowingDiscoveryEvidence,
    ValidatedBorrowingHeaderCellEvidence,
    ValidatedBorrowingHeaderEvidence,
    ValidatedBorrowingSheetEvidence,
)
from aip.product.configured.irrbb.borrowing_source_requirements import (
    BORROWING_SOURCE_REQUIREMENT_PROFILE_CODE,
    BORROWING_SOURCE_REQUIREMENT_PROFILE_VERSION,
    BorrowingSourceEvidenceAssessor,
    BorrowingSourceSchemaAssessment,
)
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE

_FILE_SHA256 = "a" * 64
_SOURCE_REFERENCE = (
    f"{BORROWING_WORKBOOK_SOURCE.source_id}:"
    f"{BORROWING_WORKBOOK_SOURCE.logical_name}#sha256={_FILE_SHA256}"
)
_OBSERVED_HEADERS = (
    "Entidad Acreedora",
    "No. Operación",
    "Operación Sistema",
    "Fecha Apertura",
    "Fecha Vencimiento",
    "Plazo",
    "Plazo restante en años",
    "Plazo restante en meses",
    "Monto Original",
    "Saldo",
    "Tasa Ponderada",
    "Tasa Interes",
    "Forma de pago ",
    "Fecha Pago",
    "Dias Vencidos",
    "Int. Pagar",
    "Int. Acumulados",
    "Dias Acum.",
    "Cuota",
    "Cuenta Capital",
    "Cuenta Int por Pagar",
    "Cuenta Gastos",
    "Destino Recursos",
    "Tasa de Referencia",
    "SPREAD",
    "Total",
    "Tasa Piso",
    "Código Tasa",
    "Tipo Calendario ",
    "TIPO GARANTIA",
    "ACTUALIZACION",
    "Fideicomiso / Custodia",
    "Fideicomiso",
    "Certificacion Auditoria",
)


def _bundle(
    headers: tuple[str, ...] = _OBSERVED_HEADERS,
    *,
    sheet_name: str = "AGO-26",
) -> BorrowingInspectionEvidenceBundle:
    cells = tuple(
        ValidatedBorrowingHeaderCellEvidence(
            column_index=index,
            column_letter=_column_letter(index),
            label=label,
        )
        for index, label in enumerate(headers, start=1)
    )
    discovery = ValidatedBorrowingDiscoveryEvidence(
        report_version="2026.09.10",
        source_id=BORROWING_WORKBOOK_SOURCE.source_id,
        source_reference=_SOURCE_REFERENCE,
        source_file_name=BORROWING_WORKBOOK_SOURCE.logical_name,
        file_sha256=_FILE_SHA256,
        sheets=(
            ValidatedBorrowingSheetEvidence(
                sheet_name=sheet_name,
                visibility="visible",
                worksheet_max_row=347,
                worksheet_max_column=len(headers),
                observed_non_empty_row_count=138,
                observed_non_empty_cell_count=2003,
                observed_last_non_empty_row=165,
                observed_last_non_empty_column=len(headers),
            ),
        ),
    )
    header = ValidatedBorrowingHeaderEvidence(
        report_version="2026.09.10",
        source_id=BORROWING_WORKBOOK_SOURCE.source_id,
        source_reference=_SOURCE_REFERENCE,
        source_file_name=BORROWING_WORKBOOK_SOURCE.logical_name,
        file_sha256=_FILE_SHA256,
        sheet_name=sheet_name,
        header_row=7,
        cells=cells,
        blank_column_indexes=(),
        duplicate_labels=(),
    )
    return BorrowingInspectionEvidenceBundle(discovery=discovery, header=header)


def _column_letter(index: int) -> str:
    value = index
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _assessment_statuses(
    result: BorrowingSourceSchemaAssessment,
) -> dict[str, IRRBBSourceAvailabilityStatus]:
    certification = result.certification
    return {item.requirement_id: item.status for item in certification.assessments}


def test_current_observed_schema_applies_confirmed_cutoff_and_repricing_rules() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle())
    statuses = _assessment_statuses(result)

    assert result.certification.profile.code == BORROWING_SOURCE_REQUIREMENT_PROFILE_CODE
    assert result.certification.profile.version == BORROWING_SOURCE_REQUIREMENT_PROFILE_VERSION
    assert result.certification.status is IRRBBSourceCertificationStatus.BLOCKED
    assert statuses["BRW_PRINCIPAL"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_START_DATE"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_MATURITY_DATE"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_CONTRACT_RATE"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_SPREAD"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_FLOOR"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_CURRENCY"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert statuses["BRW_RATE_TYPE"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert (
        statuses["BRW_NEXT_RESET_DATE"]
        is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )
    assert (
        statuses["BRW_RESET_FREQUENCY"]
        is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )
    assert statuses["BRW_CUTOFF"] is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE


def test_candidate_headers_remain_unresolved_for_unconfirmed_canonical_meaning() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle())
    statuses = _assessment_statuses(result)

    assert statuses["BRW_REFERENCE_RATE"] is IRRBBSourceAvailabilityStatus.NOT_ASSESSED
    assert statuses["BRW_PAYMENT_FREQUENCY"] is IRRBBSourceAvailabilityStatus.NOT_ASSESSED
    assert statuses["BRW_NEXT_PAYMENT_DATE"] is IRRBBSourceAvailabilityStatus.NOT_ASSESSED
    assert result.unresolved_candidate_labels == (
        "Código Tasa",
        "Tasa de Referencia",
        "Forma de pago ",
        "Fecha Pago",
    )


def test_governed_borrowing_segment_derives_liability_side() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle())
    statuses = _assessment_statuses(result)

    assert (
        statuses["BRW_BALANCE_SHEET_SIDE"]
        is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    )


def test_august_2026_sheet_derives_month_end_cutoff() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle(sheet_name="AGO-26"))
    cutoff = next(
        item for item in result.certification.assessments if item.requirement_id == "BRW_CUTOFF"
    )

    assert cutoff.status is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    assert cutoff.notes is not None
    assert "2026-08-31" in cutoff.notes


def test_invalid_sheet_label_preserves_cutoff_blocker() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle(sheet_name="AGOSTO 2026"))
    statuses = _assessment_statuses(result)

    assert statuses["BRW_CUTOFF"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_GAP


def test_fecha_apertura_fecha_pago_and_actualizacion_govern_next_reset_derivation() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle())
    reset_date = next(
        item
        for item in result.certification.assessments
        if item.requirement_id == "BRW_NEXT_RESET_DATE"
    )

    assert reset_date.status is IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE
    assert reset_date.notes is not None
    assert "Fecha Pago" in reset_date.notes
    assert "Fecha Apertura" in reset_date.notes
    assert "month after" in reset_date.notes


def test_missing_opening_date_preserves_next_reset_blocker() -> None:
    headers = tuple(label for label in _OBSERVED_HEADERS if label != "Fecha Apertura")
    result = BorrowingSourceEvidenceAssessor().assess(_bundle(headers))
    statuses = _assessment_statuses(result)

    assert statuses["BRW_START_DATE"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert statuses["BRW_NEXT_RESET_DATE"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE


def test_missing_actualizacion_preserves_next_reset_and_frequency_blockers() -> None:
    headers = tuple(label for label in _OBSERVED_HEADERS if label != "ACTUALIZACION")
    result = BorrowingSourceEvidenceAssessor().assess(_bundle(headers))
    statuses = _assessment_statuses(result)

    assert statuses["BRW_NEXT_RESET_DATE"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert statuses["BRW_RESET_FREQUENCY"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE


def test_explicit_future_headers_override_documented_derivations() -> None:
    extended = _OBSERVED_HEADERS + (
        "Moneda",
        "Tipo Tasa",
        "Fecha Reprecio",
        "Frecuencia Reprecio",
        "Fecha Corte",
    )
    result = BorrowingSourceEvidenceAssessor().assess(_bundle(extended))
    statuses = _assessment_statuses(result)

    assert statuses["BRW_CURRENCY"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_RATE_TYPE"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_NEXT_RESET_DATE"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_RESET_FREQUENCY"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_CUTOFF"] is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE
    assert statuses["BRW_REFERENCE_RATE"] is IRRBBSourceAvailabilityStatus.NOT_ASSESSED


def test_multiple_identity_candidates_fail_closed_until_identity_policy_is_governed() -> None:
    result = BorrowingSourceEvidenceAssessor().assess(_bundle())
    statuses = _assessment_statuses(result)

    assert statuses["BRW_IDENTITY"] is IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE
    assert "BRW_IDENTITY" in result.certification.blocking_requirement_ids
