from __future__ import annotations

from decimal import Decimal

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.domain.irrbb.models import IRRBBInstrumentClass
from aip.product.configured.irrbb.captaciones_irrbb_account_classifier import (
    CaptacionesIRRBBAccountClassifier,
    CaptacionesIRRBBFundingClass,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.shared.money import Currency, Money


def _fact(account: str) -> CaptacionesXMLCanonicalCurrencyFact:
    return CaptacionesXMLCanonicalCurrencyFact(
        source_record_id=f"ROW:{account}",
        source_reference=f"XML_CONFIA:Pasivos_Cuentas_Contables_210.xml|account={account}",
        creditor_id="ACR-1",
        operation_id=f"OP-{account}",
        operation_type_source_code="1",
        account_type_source_code="4",
        rate_type_source_code="V",
        accounting_account_code=account,
        amount=Money(Decimal("1000"), Currency.CRC),
    )


def test_21103_and_21204_are_governed_sight_nmd_accounts() -> None:
    for account in ("21103100", "21103200", "21204100", "21204200"):
        result = CaptacionesIRRBBAccountClassifier.classify(_fact(account))

        assert not isinstance(result, IRRBBSourceMappingFailure)
        assert result.funding_class is CaptacionesIRRBBFundingClass.SIGHT_NMD
        assert result.instrument_class is IRRBBInstrumentClass.NON_MATURITY_DEPOSIT
        assert result.rule_reference == "DIM_CUENTAS_SIPFCR_V1:CAPTACIONES"


def test_213_term_account_families_map_to_term_deposit_without_capf_inference() -> None:
    for account in ("21301100", "21301200", "21302100", "21302200", "21312100", "21312200", "21314100", "21314200"):
        result = CaptacionesIRRBBAccountClassifier.classify(_fact(account))

        assert not isinstance(result, IRRBBSourceMappingFailure)
        assert result.funding_class is CaptacionesIRRBBFundingClass.TERM_DEPOSIT
        assert result.instrument_class is IRRBBInstrumentClass.TERM_DEPOSIT


def test_21104_matured_term_is_kept_separate_and_not_promoted_to_active_term_deposit() -> None:
    result = CaptacionesIRRBBAccountClassifier.classify(_fact("21104100"))

    assert not isinstance(result, IRRBBSourceMappingFailure)
    assert result.funding_class is CaptacionesIRRBBFundingClass.TERM_MATURED
    assert result.instrument_class is None


def test_unknown_account_family_fails_closed() -> None:
    result = CaptacionesIRRBBAccountClassifier.classify(_fact("21400100"))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.canonical_field == "accounting_account_code"
    assert "Unsupported Captaciones accounting account family" in result.message


def test_non_numeric_account_text_fails_closed() -> None:
    result = CaptacionesIRRBBAccountClassifier.classify(_fact("213-12-1"))

    assert isinstance(result, IRRBBSourceMappingFailure)
    assert "canonical numeric text" in result.message
