from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TypeAlias

from aip.application.irrbb import IRRBBSourceMappingFailure, IRRBBSourceMappingFailureCode
from aip.domain.irrbb.models import RateType
from aip.product.configured.irrbb.captaciones_capf_contractual import CaptacionesCAPFContractualFact
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.shared.money import Currency, Money

CAPF_CERTIFICATE_OPERATION_RULE_REFERENCE = (
    "CAPF_CERTIFICATE_EQUALS_OPERATION@1|"
    "Informe_Reconstruccion_Brechas_Tasas_Agosto_2026:4.3|"
    "Especificacion_Tecnico_Funcional_Motor_Brechas_SICVECA_205_Actualizada:v2.0:8.1"
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
        operation_id = self.xml_fact.operation_id
        if not operation_id.strip() or operation_id != operation_id.strip():
            raise ValueError("CAPF joined fact operation_id must be nonempty canonical text")
        if operation_id != self.contractual_fact.certificate_number:
            raise ValueError("CAPF joined fact requires Número Certificado = IdOperacion")
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


CaptacionesCAPFJoinResult: TypeAlias = CaptacionesCAPFJoinedFact | IRRBBSourceMappingFailure


class CaptacionesCAPFOperationJoinService:
    """Join selected CAPF facts by the documented exact certificate/operation key.

    Inputs must already preserve canonical source text. No numeric conversion,
    zero stripping, case folding or per-certificate correspondence is applied.
    """

    def join(
        self,
        *,
        xml_fact: CaptacionesXMLCanonicalCurrencyFact,
        contractual_facts_by_certificate: Mapping[str, CaptacionesCAPFContractualFact],
    ) -> CaptacionesCAPFJoinResult:
        operation_id = xml_fact.operation_id
        if not operation_id.strip() or operation_id != operation_id.strip():
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                canonical_field="operation_id",
                message="CAPF XML operation_id must be nonempty canonical source text.",
            )

        contractual_fact = contractual_facts_by_certificate.get(operation_id)
        if contractual_fact is None:
            return self._failure(
                xml_fact,
                code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
                canonical_field="capf_contractual_record",
                message=(
                    f"No CAPF certificate matches XML operation {operation_id!r} by "
                    f"Número Certificado = IdOperacion under "
                    f"{CAPF_CERTIFICATE_OPERATION_RULE_REFERENCE}."
                ),
            )
        if contractual_fact.certificate_number != operation_id:
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
            binding_reference=(
                f"{CAPF_CERTIFICATE_OPERATION_RULE_REFERENCE}|"
                f"operation={operation_id}|certificate={contractual_fact.certificate_number}"
            ),
            risk_date=contractual_fact.maturity_date,
            contractual_rate_type=RateType.FIXED,
        )

    @staticmethod
    def index_contractual_facts(
        facts: tuple[CaptacionesCAPFContractualFact, ...],
    ) -> Mapping[str, CaptacionesCAPFContractualFact]:
        result: dict[str, CaptacionesCAPFContractualFact] = {}
        for fact in facts:
            certificate = fact.certificate_number
            if not certificate.strip() or certificate != certificate.strip():
                raise ValueError("CAPF certificate numbers must be nonempty canonical text")
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
