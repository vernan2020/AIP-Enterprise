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
from aip.product.configured.irrbb.borrowing_source_rules import (
    BORROWING_CUTOFF_RULE_REFERENCE,
    BORROWING_NEXT_RESET_RULE_REFERENCE,
    BORROWING_QUARTERLY_PHASE_RULE_REFERENCE,
    BORROWING_RESET_DAY_RULE_REFERENCE,
    BORROWING_RESET_FREQUENCY_RULE_REFERENCE,
    BorrowingSourceRules,
)
from aip.product.configured.irrbb.physical_source_registry import BORROWING_WORKBOOK_SOURCE

BORROWING_SOURCE_REQUIREMENT_PROFILE_CODE = "COOPEALIANZA_IRRBB_BORROWINGS"
BORROWING_SOURCE_REQUIREMENT_PROFILE_VERSION = "2026.09.14"
BORROWING_BALANCE_SHEET_SIDE_RULE_REFERENCE = (
    "aip://irrbb/source-rules/borrowings/balance-sheet-side-liability/v1"
)


@dataclass(frozen=True, slots=True)
class BorrowingSourceSchemaAssessment:
    """Evidence-backed borrowing-source assessment without contractual row extraction."""

    certification: IRRBBSourceCertificationReport
    observed_labels: tuple[str, ...]
    unresolved_candidate_labels: tuple[str, ...]


class BorrowingSourceEvidenceAssessor:
    """Assess governed borrowing workbook evidence against RTILB requirements.

    Header presence can prove an explicitly named native field. Institutionally
    confirmed source semantics may also support a documented derivation rule, but
    the assessor remains fail-closed whenever row-level evidence or an exact date
    cannot yet be established.
    """

    _PROFILE = IRRBBSourceRequirementProfile(
        code=BORROWING_SOURCE_REQUIREMENT_PROFILE_CODE,
        version=BORROWING_SOURCE_REQUIREMENT_PROFILE_VERSION,
        effective_from=date(2026, 9, 14),
        source_reference=("aip://irrbb/source-profiles/coopealianza/borrowings/2026.09.14"),
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
        """Return the effective borrowing-source requirement profile."""

        return cls._PROFILE

    def assess(self, bundle: BorrowingInspectionEvidenceBundle) -> BorrowingSourceSchemaAssessment:
        """Classify exact observed headers and approved documented derivations."""

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
                    "aip://irrbb/physical-source-registry/" f"{BORROWING_WORKBOOK_SOURCE.source_id}"
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
                candidates=("Código Tasa", "Tasa básica Pasiva", "Tasa de Referencia"),
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
            self._next_reset_assessment(by_label=by_label, bundle=bundle),
            self._reset_frequency_assessment(by_label=by_label, bundle=bundle),
            self._cutoff_assessment(by_label=by_label, bundle=bundle),
        )
        certification = IRRBBSourceCertificationService.certify(
            profile=self._PROFILE,
            assessments=assessments,
        )
        unresolved_candidates = tuple(
            label
            for label in (
                "Código Tasa",
                "Tasa básica Pasiva",
                "Tasa de Referencia",
                "Forma de pago ",
                "Fecha Pago",
            )
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
        matches = [cell for candidate in candidates for cell in by_label.get(candidate, ())]
        if len(matches) == 1:
            cell = matches[0]
            return IRRBBSourceRequirementAssessment(
                requirement_id=requirement_id,
                status=IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE,
                source_reference=bundle.header.source_reference,
                evidence_reference=BorrowingSourceEvidenceAssessor._header_evidence_reference(
                    bundle=bundle,
                    cell=cell,
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

    def _reset_frequency_assessment(
        self,
        *,
        by_label: dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]],
        bundle: BorrowingInspectionEvidenceBundle,
    ) -> IRRBBSourceRequirementAssessment:
        native = self._native(
            requirement_id="BRW_RESET_FREQUENCY",
            label="Frecuencia Reprecio",
            by_label=by_label,
            bundle=bundle,
            missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
        )
        if native.status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE:
            return native

        matches = by_label.get("ACTUALIZACION", ())
        if len(matches) != 1:
            return native
        cell = matches[0]
        return IRRBBSourceRequirementAssessment(
            requirement_id="BRW_RESET_FREQUENCY",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=bundle.header.source_reference,
            derivation_rule_reference=BORROWING_RESET_FREQUENCY_RULE_REFERENCE,
            evidence_reference=self._header_evidence_reference(bundle=bundle, cell=cell),
            notes=(
                "Institutional policy confirms that ACTUALIZACION is the contractual "
                "repricing cadence; supported source values remain strict and fail closed."
            ),
        )

    def _next_reset_assessment(
        self,
        *,
        by_label: dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]],
        bundle: BorrowingInspectionEvidenceBundle,
    ) -> IRRBBSourceRequirementAssessment:
        native = self._native(
            requirement_id="BRW_NEXT_RESET_DATE",
            label="Fecha Reprecio",
            by_label=by_label,
            bundle=bundle,
            missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_EVE,
        )
        if native.status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE:
            return native

        opening_date = by_label.get("Fecha Apertura", ())
        payment_day = by_label.get("Fecha Pago", ())
        frequency = by_label.get("ACTUALIZACION", ())
        if len(opening_date) != 1 or len(payment_day) != 1 or len(frequency) != 1:
            return native
        return IRRBBSourceRequirementAssessment(
            requirement_id="BRW_NEXT_RESET_DATE",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=bundle.header.source_reference,
            derivation_rule_reference=BORROWING_NEXT_RESET_RULE_REFERENCE,
            evidence_reference=(
                self._header_evidence_reference(bundle=bundle, cell=opening_date[0])
                + ";"
                + self._header_evidence_reference(bundle=bundle, cell=payment_day[0])
                + ";"
                + self._header_evidence_reference(bundle=bundle, cell=frequency[0])
                + f";{bundle.header.source_reference}|sheet={bundle.header.sheet_name}"
            ),
            notes=(
                "Institutional policy confirms repricing occurs on the Fecha Pago day "
                f"({BORROWING_RESET_DAY_RULE_REFERENCE}); ACTUALIZACION supplies cadence "
                f"({BORROWING_RESET_FREQUENCY_RULE_REFERENCE}); and quarterly cadence uses "
                "Fecha Apertura as its phase anchor, with repricing effective in the month "
                "after each completed three-month period "
                f"({BORROWING_QUARTERLY_PHASE_RULE_REFERENCE}). The monthly worksheet cutoff "
                f"is governed by {BORROWING_CUTOFF_RULE_REFERENCE}. Row values remain subject "
                "to strict validation; unsupported cadence or impossible calendar dates fail closed."
            ),
        )

    def _cutoff_assessment(
        self,
        *,
        by_label: dict[str, tuple[ValidatedBorrowingHeaderCellEvidence, ...]],
        bundle: BorrowingInspectionEvidenceBundle,
    ) -> IRRBBSourceRequirementAssessment:
        native = self._native(
            requirement_id="BRW_CUTOFF",
            label="Fecha Corte",
            by_label=by_label,
            bundle=bundle,
            missing_status=IRRBBSourceAvailabilityStatus.MISSING_BLOCKING_GAP,
        )
        if native.status is IRRBBSourceAvailabilityStatus.NATIVE_AVAILABLE:
            return native

        cutoff = BorrowingSourceRules.month_end_cutoff(bundle.header.sheet_name)
        if cutoff is None:
            return native
        return IRRBBSourceRequirementAssessment(
            requirement_id="BRW_CUTOFF",
            status=IRRBBSourceAvailabilityStatus.DERIVABLE_WITH_DOCUMENTED_RULE,
            source_reference=bundle.header.source_reference,
            derivation_rule_reference=BORROWING_CUTOFF_RULE_REFERENCE,
            evidence_reference=(
                f"{bundle.header.source_reference}|sheet={bundle.header.sheet_name}"
            ),
            notes=(
                "Institutional policy confirms each governed monthly worksheet is a "
                f"month-end snapshot; derived cutoff={cutoff.isoformat()}."
            ),
        )

    @staticmethod
    def _header_evidence_reference(
        *,
        bundle: BorrowingInspectionEvidenceBundle,
        cell: ValidatedBorrowingHeaderCellEvidence,
    ) -> str:
        return (
            f"{bundle.header.source_reference}|sheet={bundle.header.sheet_name}"
            f"|header_row={bundle.header.header_row}|column={cell.column_letter}"
            f"|label={cell.label}"
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
                "yet governed for this canonical variable: " + ", ".join(observed)
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
