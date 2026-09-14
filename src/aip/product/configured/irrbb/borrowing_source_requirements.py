from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from aip.application.irrbb.source_certification import (
    IRRBBSourceAvailabilityStatus,
    IRRBBSourceCertificationReport,
    IRRBBSourceCertificationService,
    IRRBBSourcePerimeter,
    IRRBBSourceRequirement,
    IRRBBSourceRequirementAssessment,
    IRRBBSourceRequirementProfile,
)
from aip.product.configured.irrbb.borrowing_inspection_evidence import (
    BorrowingInspectionEvidenceBundle,
    ValidatedBorrowingHeaderCellEvidence,
)
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE

BORROWING_SOURCE_REQUIREMENT_PROFILE_CODE = "COOPEALIANZA_IRRBB_BORROWINGS"
BORROWING_SOURCE_REQUIREMENT_PROFILE_VERSION = "2026.09.13"
BORROWING_BALANCE_SHEET_SIDE_RULE_REFERENCE = (
    "aip://irrbb/source-rules/borrowings/balance-sheet-side-liability/v1"
)


@dataclass(frozen=True, slots=True)
class BorrowingSourceSchemaAssessment:
    """Evidence-backed Phase 19 assessment without reading contractual data rows."""

    certification: IRRBBSourceCertificationReport
    observed_labels: tuple[str, ...]
    unresolved_candidate_labels: tuple[str, ...]


class BorrowingSourceEvidenceAssessor:
    """Assess the governed borrowing workbook schema against RTILB requirements.

    This boundary deliberately consumes only validated Phase 18 discovery/header
    evidence. Header presence can prove that an explicitly named source field exists,
    but it cannot silently promote ambiguous labels into contractual semantics.
    Currency, rate type, payment frequency, reset timing and cutoff therefore remain
    fail-closed unless their exact governed fields are evidenced.
    """

    _PROFILE = IRRBBSourceRequirementProfile(
        code=BORROWING_SOURCE_REQUIREMENT_PROFILE_CODE,
        version=BORROWING_SOURCE_REQUIREMENT_PROFILE_VERSION,
        effective_from=date(2026, 9, 13),
        source_reference=(
            "aip://irrbb/source-profiles/coopealianza/borrowings/2026.09.13"
        ),
        requirements=(
            IRRBBSourceRequirement(
                requirement_id="BRW_IDENTITY",
                canonical_variable="position_id",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Stable borrowing-operation identity.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_PRINCIPAL",
                canonical_variable="principal",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Outstanding contractual principal balance.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_CURRENCY",
                canonical_variable="currency",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contract currency without a default or inferred value.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_BALANCE_SHEET_SIDE",
                canonical_variable="balance_sheet_side",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Liability-side classification from the governed borrowing source.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_START_DATE",
                canonical_variable="start_date",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contract opening/start date.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_MATURITY_DATE",
                canonical_variable="maturity_date",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contractual maturity date.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_RATE_TYPE",
                canonical_variable="rate_type",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Explicit fixed/floating rate classification.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_CONTRACT_RATE",
                canonical_variable="contract_rate",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Current contractual interest rate.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_REFERENCE_RATE",
                canonical_variable="reference_rate",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Floating-rate benchmark identity where applicable.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_SPREAD",
                canonical_variable="spread",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contractual spread over the floating-rate benchmark.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_FLOOR",
                canonical_variable="floor",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contractual interest-rate floor where applicable.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_PAYMENT_FREQUENCY",
                canonical_variable="payment_frequency",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contractual interest/principal payment frequency.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_NEXT_PAYMENT_DATE",
                canonical_variable="next_payment_date",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Next contractual payment date when natively available.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_NEXT_RESET_DATE",
                canonical_variable="next_reset_date",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Next contractual rate reset/repricing date for floating positions.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_RESET_FREQUENCY",
                canonical_variable="reset_frequency",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Contractual repricing frequency for floating positions.",
            ),
            IRRBBSourceRequirement(
                requirement_id="BRW_CUTOFF",
                canonical_variable="cutoff_date",
                perimeter=IRRBBSourcePerimeter.LIABILITY,
                description="Explicit valuation/source cutoff for the inspected snapshot.",
            ),
        ),
    )

    @classmethod
    def requirement_profile(cls) -> IRRBBSourceRequirementProfile:
        """Return the effective Phase 19 borrowing requirement profile."""

        return cls._PROFILE

    def assess(self, bundle: BorrowingInspectionEvidenceBundle) -> BorrowingSourceSchemaAssessment:
        """Classify exact observed headers without assigning unsupported semantics."""

        self._validate_bundle_identity(bundle)
        labels = tuple(cell.label for cell in bundle.header.cells if cell.label is not None)
        by_label = self._index_cells(bundle.header.cells)
        source_reference = bundle.header.source_reference

        assessments = (
            self._native_any(
                requirement_id="BRW_IDENTITY",
                candidates=("No. Operación", "Operación Sistema"),
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_PRINCIPAL",
                label="Saldo",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_CURRENCY",
                label="Moneda",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            IRRBBSourceRequirementAssessment(
                requirement_id="BRW_BALANCE_SHEET_SIDE",
                status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
                source_reference=source_reference,
                derivation_rule_reference=BORROWING_BALANCE_SHEET_SIDE_RULE_REFERENCE,
                evidence_reference=(
                    "aip://irrbb/physical-source-registry/"
                    f"{BORROWING_WORKBOOK_SOURCE.source_id}"
                ),
                notes="The governed borrowing source is mapped to the LIABILITY perimeter.",
            ),
            self._native(
                requirement_id="BRW_START_DATE",
                label="Fecha Apertura",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_MATURITY_DATE",
                label="Fecha Vencimiento",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_RATE_TYPE",
                label="Tipo Tasa",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_CONTRACT_RATE",
                label="Tasa Interes",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._unresolved_candidate(
                requirement_id="BRW_REFERENCE_RATE",
                candidates=("Código Tasa", "Tasa básica Pasiva"),
                by_label=by_label,
            ),
            self._native(
                requirement_id="BRW_SPREAD",
                label="SPREAD",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
            ),
            self._native(
                requirement_id="BRW_FLOOR",
                label="Tasa Piso",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
            ),
            self._unresolved_candidate(
                requirement_id="BRW_PAYMENT_FREQUENCY",
                candidates=("Forma de pago ",),
                by_label=by_label,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._unresolved_candidate(
                requirement_id="BRW_NEXT_PAYMENT_DATE",
                candidates=("Fecha Pago",),
                by_label=by_label,
            ),
            self._native(
                requirement_id="BRW_NEXT_RESET_DATE",
                label="Fecha Reprecio",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_RESET_FREQUENCY",
                label="Frecuencia Reprecio",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
            ),
            self._native(
                requirement_id="BRW_CUTOFF",
                label="Fecha Corte",
                by_label=by_label,
                bundle=bundle,
                missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_GAP,
            ),
        )
        certification = IRRBBSourceCertificationService.certify(
            profile=self._PROFILE,
            assessments=assessments,
        )
        unresolved_candidates = tuple(
            label
            for label in ("Código Tasa", "Tasa básica Pasiva", "Forma de pago ", "Fecha Pago")
            if label in by_label
        )
        return BorrowingSourceSchemaAssessment(
            certification=certification,
            observed_labels=labels,
            unresolved_candidate_labels=unresolved_candidates,
        )

    @staticmethod
    def _validate_bundle_identity(bundle: BorrowingInspectionEvidenceBundle) -> None:
        if bundle.discovery.source_reference != bundle.header.source_reference:
            raise ValueError("borrowing evidence bundle source references do not match")
        if bundle.header.source_id != BORROWING_WORKBOOK_SOURCE.source_id:
            raise ValueError("borrowing evidence bundle is not the governed physical source")
        if bundle.header.source_file_name != BORROWING_WORKBOOK_SOURCE.logical_name:
            raise ValueError("borrowing evidence bundle filename is not the governed workbook")

    @staticmethod
    def _index_cells(
        cells: tuple[ValidatedBorrowingHeaderCellEvidence, ...],
    ) -> dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]]:
        indexed: dict[str, list[ValidatedBorrowingHeaderCellEvidence]] = {}
        for cell in cells:
            if cell.label is None:
                continue
            indexed.setdefault(cell.label, []).append(cell)
        return {label: tuple(matches) for label, matches in indexed.items()}

    def _native(
        self,
        *,
        requirement_id: str,
        label: str,
        by_label: dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]],
        bundle: BorrowingInspectionEvidenceBundle,
        missing_status: IRRBBSourceAvailabilityStatus,
    ) -> IRRBBSourceRequirementAssessment:
        return self._native_any(
            requirement_id=requirement_id,
            candidates=(label,),
            by_label=by_label,
            bundle=bundle,
            missing_status=missing_status,
        )

    @staticmethod
    def _native_any(
        *,
        requirement_id: str,
        candidates: tuple[str, ...],
        by_label: dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]],
        bundle: BorrowingInspectionEvidenceBundle,
        missing_status: IRRBBSourceAvailabilityStatus,
    ) -> IRRBBSourceRequirementAssessment:
        matches = [
            cell
            for candidate in candidates
            for cell in by_label.get(candidate, ())
        ]
        if len(matches) == 1:
            cell = matches[0]
            return IRRBBSourceRequirementAssessment(
                requirement_id=requirement_id,
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference=bundle.header.source_reference,
                evidence_reference=(
                    f"{bundle.header.source_reference}|sheet={bundle.header.sheet_name}"
                    f"|header_row={bundle.header.header_row}|column={cell.column_letter}"
                    f"|label={cell.label}"
                ),
            )
        notes = (
            "No exact governed header was observed."
            if not matches
            else "Multiple candidate headers were observed; mapping is ambiguous."
        )
        return IRRBBSourceRequirementAssessment(
            requirement_id=requirement_id,
            status=missing_status,
            notes=notes,
        )

    @staticmethod
    def _unresolved_candidate(
        *,
        requirement_id: str,
        candidates: tuple[str, ...],
        by_label: dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]],
        missing_status: IRRBBSourceAvailabilityStatus = IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
    ) -> IRRBBSourceRequirementAssessment:
        observed = tuple(candidate for candidate in candidates if candidate in by_label)
        if observed:
            notes = (
                "Candidate source header(s) observed but contractual semantic mapping is not "
                "yet governed: " + ", ".join(observed)
            )
            return IRRBBSourceRequirementAssessment(
                requirement_id=requirement_id,
                status=IRRBBSourceAvailabilityStatus.NOT_ASSESSED,
                notes=notes,
            )
        return IRRBBSourceRequirementAssessment(
            requirement_id=requirement_id,
            status=missing_status,
            notes="No exact governed header or approved semantic derivation rule was observed.",
        )
