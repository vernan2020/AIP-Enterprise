from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.domain.irrbb.models import IRRBBInstrumentClass
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)


class CaptacionesIRRBBFundingClass(str, Enum):
    """Institutional Captaciones classification before 19-band scheduling."""

    SIGHT_NMD = "SIGHT_NMD"
    TERM_DEPOSIT = "TERM_DEPOSIT"
    TERM_MATURED = "TERM_MATURED"


@dataclass(frozen=True, slots=True)
class CaptacionesIRRBBAccountClassification:
    """Auditable account-family classification for one Captaciones record."""

    source_record_id: str
    source_reference: str
    operation_id: str
    accounting_account_code: str
    funding_class: CaptacionesIRRBBFundingClass
    instrument_class: IRRBBInstrumentClass | None
    rule_reference: str


CaptacionesIRRBBAccountClassificationResult = (
    CaptacionesIRRBBAccountClassification | IRRBBSourceMappingFailure
)


class CaptacionesIRRBBAccountClassifier:
    """Classify governed Captaciones account families without behavioral inference.

    Evidence basis:
    - 211-03 and 212-04 are obligations with the public at sight.
    - 213-01/02/12/14 are term deposits/captaciones.
    - 211-04 is matured term funding and remains a separate blocked category.

    This classifier does not assign a 19-band bucket. NMDs require an approved
    behavioral profile and term deposits require their contractual schedule.
    """

    RULE_REFERENCE = "DIM_CUENTAS_SIPFCR_V1:CAPTACIONES"

    _SIGHT_PREFIXES = ("21103", "21204")
    _TERM_PREFIXES = ("21301", "21302", "21312", "21314")
    _MATURED_TERM_PREFIXES = ("21104",)

    @classmethod
    def classify(
        cls,
        fact: CaptacionesXMLCanonicalCurrencyFact,
    ) -> CaptacionesIRRBBAccountClassificationResult:
        account = fact.accounting_account_code.strip()
        if not account:
            return cls._failure(fact, "accounting_account_code is required")
        if not account.isdigit():
            return cls._failure(
                fact,
                "Captaciones accounting account must be canonical numeric text.",
            )

        if account.startswith(cls._SIGHT_PREFIXES):
            return CaptacionesIRRBBAccountClassification(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                operation_id=fact.operation_id,
                accounting_account_code=account,
                funding_class=CaptacionesIRRBBFundingClass.SIGHT_NMD,
                instrument_class=IRRBBInstrumentClass.NON_MATURITY_DEPOSIT,
                rule_reference=cls.RULE_REFERENCE,
            )

        if account.startswith(cls._TERM_PREFIXES):
            return CaptacionesIRRBBAccountClassification(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                operation_id=fact.operation_id,
                accounting_account_code=account,
                funding_class=CaptacionesIRRBBFundingClass.TERM_DEPOSIT,
                instrument_class=IRRBBInstrumentClass.TERM_DEPOSIT,
                rule_reference=cls.RULE_REFERENCE,
            )

        if account.startswith(cls._MATURED_TERM_PREFIXES):
            return CaptacionesIRRBBAccountClassification(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                operation_id=fact.operation_id,
                accounting_account_code=account,
                funding_class=CaptacionesIRRBBFundingClass.TERM_MATURED,
                instrument_class=None,
                rule_reference=cls.RULE_REFERENCE,
            )

        return cls._failure(
            fact,
            f"Unsupported Captaciones accounting account family: {account}.",
        )

    @classmethod
    def _failure(
        cls,
        fact: CaptacionesXMLCanonicalCurrencyFact,
        message: str,
    ) -> IRRBBSourceMappingFailure:
        return IRRBBSourceMappingFailure(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            code=IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE,
            canonical_field="accounting_account_code",
            message=message,
        )
