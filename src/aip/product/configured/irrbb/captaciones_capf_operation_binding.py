from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TypeAlias

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import RateType
from aip.product.configured.irrbb.captaciones_capf_contractual import (
    CaptacionesCAPFContractualFact,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFOperationBinding:
    """One institutionally evidenced certificate-to-XML-operation relationship."""

    certificate_number: str
    operation_id: str
    evidence_reference: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("certificate_number", self.certificate_number),
            ("operation_id", self.operation_id),
            ("evidence_reference", self.evidence_reference),
        ):
            if not value.strip():
                raise ValueError(f"CAPF operation binding {field_name} is required")
            if value != value.strip():
                raise ValueError(f"CAPF operation binding {field_name} must be canonical text")


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFOperationBindingCatalog:
    """Versioned and fail-closed CAPF certificate-to-operation bindings.

    The catalog deliberately has no default transformation. In particular,
    certificate number equality with XML IdOperacion is never assumed.
    """

    code: str
    version: str
    evidence_reference: str
    bindings: tuple[CaptacionesCAPFOperationBinding, ...]

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("CAPF operation binding catalog code is required")
        if not self.version.strip():
            raise ValueError("CAPF operation binding catalog version is required")
        if not self.evidence_reference.strip():
            raise ValueError("CAPF operation binding catalog evidence_reference is required")
        if not self.bindings:
            raise ValueError("CAPF operation binding catalog requires evidenced bindings")

        certificate_numbers = tuple(item.certificate_number for item in self.bindings)
        operation_ids = tuple(item.operation_id for item in self.bindings)
        if len(certificate_numbers) != len(set(certificate_numbers)):
            raise ValueError("CAPF operation binding certificate numbers must be unique")
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("CAPF operation binding operation ids must be unique")

    @property
    def reference(self) -> str:
        return f"{self.code}@{self.version}|{self.evidence_reference}"

    def resolve_operation(self, operation_id: str) -> CaptacionesCAPFOperationBinding:
        canonical = operation_id.strip()
        if not canonical:
            raise ValueError("CAPF XML operation_id is required")
        if operation_id != canonical:
            raise ValueError("CAPF XML operation_id must be canonical text")
        for binding in self.bindings:
            if binding.operation_id == canonical:
                return binding
        raise KeyError(f"unmapped CAPF XML operation_id: {canonical}")

    def binding_reference(self, binding: CaptacionesCAPFOperationBinding) -> str:
        return (
            f"{self.reference}|operation={binding.operation_id}|"
            f"certificate={binding.certificate_number}|{binding.evidence_reference}"
        )


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFJoinedFact:
    """Auditable XML principal plus contractual CAPF evidence before bucketing."""

    xml_fact: CaptacionesXMLCanonicalCurrencyFact
    contractual_fact: CaptacionesCAPFContractualFact
    binding_reference: str
    risk_date: date
    contractual_rate_type: RateType

    def __post_init__(self) -> None:
        if not self.binding_reference.strip():
            raise ValueError("CAPF joined fact binding_reference is required")
        if self.xml_fact.operation_id not in self.binding_reference:
            raise ValueError("CAPF joined fact binding must identify the XML operation")
        if self.contractual_fact.certificate_number not in self.binding_reference:
            raise ValueError("CAPF joined fact binding must identify the certificate")
        if self.risk_date != self.contractual_fact.maturity_date:
            raise ValueError("CAPF joined fact risk_date must be contractual maturity")
        if self.contractual_rate_type is not RateType.FIXED:
            raise ValueError("governed CAPF joined facts must be fixed-rate")

    @property
    def operation_id(self) -> str:
        return self.xml_fact.operation_id

    @property
    def certificate_number(self) -> str:
        return self.contractual_fact.certificate_number

    @property
    def principal(self) -> Money:
        """Canonical principal comes only from Pasivos 210, never the colonized XLSX amount."""

        return self.xml_fact.principal

    @property
    def currency(self) -> Currency:
        return self.xml_fact.principal.currency


CaptacionesCAPFJoinResult: TypeAlias = (
    CaptacionesCAPFJoinedFact | IRRBBSourceMappingFailure
)


class CaptacionesCAPFOperationJoinService:
    """Join one explicitly selected CAPF XML fact through governed evidence only."""

    def __init__(self, *, catalog: CaptacionesCAPFOperationBindingCatalog) -> None:
        self._catalog = catalog

    def join(
        self,
        *,
        xml_fact: CaptacionesXMLCanonicalCurrencyFact,
        contractual_facts_by_certificate: Mapping[str, CaptacionesCAPFContractualFact],
    ) -> CaptacionesCAPFJoinResult:
        try:
            binding = self._catalog.resolve_operation(xml_fact.operation_id)
        except KeyError:
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="capf_contractual_binding",
                message=(
                    "No governed CAPF certificate binding exists for XML operation "
                    f"{xml_fact.operation_id!r} under {self._catalog.reference}; "
                    "Número Certificado equality with IdOperacion is not assumed."
                ),
            )

        contractual_fact = contractual_facts_by_certificate.get(binding.certificate_number)
        if contractual_fact is None:
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="capf_contractual_record",
                message=(
                    "Governed CAPF binding references certificate "
                    f"{binding.certificate_number!r}, but that certificate is absent from "
                    "the contractual workbook cut."
                ),
            )
        if contractual_fact.certificate_number != binding.certificate_number:
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                canonical_field="certificate_number",
                message="CAPF contractual index substituted the governed certificate identity.",
            )

        if contractual_fact.contractual_rate_type is not RateType.FIXED:
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                canonical_field="rate_type",
                message=(
                    "CAPF contractual evidence conflicts with the fixed-rate " "institutional rule."
                ),
            )
        if xml_fact.rate_type_source_code.strip().upper() != "F":
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                canonical_field="rate_type",
                message=(
                    "Pasivos 210 rate type conflicts with the institutional rule that all "
                    "CAP records are fixed-rate."
                ),
            )

        if (
            xml_fact.maturity_date is not None
            and xml_fact.maturity_date != contractual_fact.maturity_date
        ):
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                canonical_field="maturity_date",
                message=(
                    "Pasivos 210 and the CAPF contractual workbook provide conflicting "
                    "maturity dates; neither date was selected."
                ),
            )

        return CaptacionesCAPFJoinedFact(
            xml_fact=xml_fact,
            contractual_fact=contractual_fact,
            binding_reference=self._catalog.binding_reference(binding),
            risk_date=contractual_fact.maturity_date,
            contractual_rate_type=RateType.FIXED,
        )

    @staticmethod
    def index_contractual_facts(
        facts: tuple[CaptacionesCAPFContractualFact, ...],
    ) -> Mapping[str, CaptacionesCAPFContractualFact]:
        result: dict[str, CaptacionesCAPFContractualFact] = {}
        for fact in facts:
            if fact.certificate_number in result:
                raise ValueError("CAPF contractual certificate numbers must be unique")
            result[fact.certificate_number] = fact
        return result

    @staticmethod
    def _failure(
        xml_fact: CaptacionesXMLCanonicalCurrencyFact,
        *,
        code: IRRBBSourceMappingFailureCode,
        canonical_field: str,
        message: str,
    ) -> IRRBBSourceMappingFailure:
        return IRRBBSourceMappingFailure(
            source_record_id=xml_fact.source_record_id,
            source_reference=xml_fact.source_reference,
            code=code,
            canonical_field=canonical_field,
            message=message,
        )
