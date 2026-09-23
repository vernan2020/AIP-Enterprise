from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.product.configured.irrbb.borrowing_xml_batch_bridge import (
    BorrowingXMLNormalizationBatchResult,
)
from aip.product.configured.irrbb.borrowing_xml_currency_bridge import (
    BorrowingXMLCurrencyBridge,
)
from aip.product.configured.irrbb.borrowing_xml_currency_catalog import (
    BorrowingXMLCurrencyCatalog,
    BorrowingXMLCurrencyCodeBinding,
)
from aip.product.configured.irrbb.borrowing_xml_normalizer import BorrowingXMLFact
from aip.shared.money import Currency


def _catalog() -> BorrowingXMLCurrencyCatalog:
    return BorrowingXMLCurrencyCatalog(
        code="TEST-OBLIGACIONES-CURRENCY",
        version="1",
        evidence_reference="TEST:EVIDENCE:CATALOG",
        bindings=(
            BorrowingXMLCurrencyCodeBinding(
                source_code="SRC-MN",
                currency=Currency.CRC,
                evidence_reference="TEST:EVIDENCE:SRC-MN",
            ),
            BorrowingXMLCurrencyCodeBinding(
                source_code="SRC-ME",
                currency=Currency.USD,
                evidence_reference="TEST:EVIDENCE:SRC-ME",
            ),
        ),
    )


def _fact(
    *,
    record_id: str,
    currency_code: str,
    principal_amount: Decimal = Decimal("1000"),
    contracted_amount: Decimal | None = Decimal("1500"),
    product_amount: Decimal | None = Decimal("10"),
) -> BorrowingXMLFact:
    return BorrowingXMLFact(
        source_record_id=f"XML_CONFIA:obligaciones.xml:record:{record_id}",
        source_reference=f"XML_CONFIA:obligaciones.xml|record={record_id}",
        creditor_id="ACREEDOR",
        operation_id=f"OP-{record_id}",
        operation_type_source_code="OP-TYPE",
        guarantee_indicator="N",
        currency_source_code=currency_code,
        obligation_indicator="L",
        revolving_indicator="S",
        credit_line_id="LINE-1",
        conditional_indicator="N",
        country_source_code="CR",
        contract_currency_source_code="CONTRACT-CURRENCY-SOURCE",
        disbursement_currency_source_code="DISBURSEMENT-CURRENCY-SOURCE",
        rate_type_source_code="RATE-TYPE",
        variable_rate_source_code="4",
        nominal_rate_percent=Decimal("4.25"),
        sugef_catalog_source_code="14",
        accounting_account_code="23221100",
        principal_amount=principal_amount,
        contracted_amount=contracted_amount,
        product_account_code="23801100" if product_amount is not None else None,
        product_amount=product_amount,
        origination_date=date(2024, 9, 23),
        maturity_date=date(2038, 8, 13),
        next_principal_payment_date=date(2026, 10, 20),
        next_interest_payment_date=date(2026, 9, 20),
        principal_payment_frequency_source_code="12",
        interest_payment_frequency_source_code="4",
    )


def _batch(
    *facts: BorrowingXMLFact,
    failures: tuple[IRRBBSourceMappingFailure, ...] = (),
) -> BorrowingXMLNormalizationBatchResult:
    return BorrowingXMLNormalizationBatchResult(
        cutoff_date=date(2026, 8, 31),
        source_file_name="Pasivos_Cuentas_Contables_220_230_260_270_280.xml",
        source_sha256="b" * 64,
        source_record_count=len(facts) + len(failures),
        normalized_facts=tuple(facts),
        mapping_failures=failures,
    )


def test_catalog_resolves_only_explicit_governed_bindings() -> None:
    catalog = _catalog()

    assert catalog.resolve("SRC-MN") is Currency.CRC
    assert catalog.resolve("SRC-ME") is Currency.USD


def test_catalog_has_no_default_mapping_for_observed_numeric_codes() -> None:
    catalog = _catalog()

    with pytest.raises(KeyError, match="unmapped Obligaciones XML currency source code: 1"):
        catalog.resolve("1")

    with pytest.raises(KeyError, match="unmapped Obligaciones XML currency source code: 2"):
        catalog.resolve("2")


def test_bridge_preserves_contractual_lineage_after_currency_translation() -> None:
    result = BorrowingXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(_fact(record_id="1", currency_code="SRC-MN"))
    )

    assert not result.mapping_failures
    assert len(result.canonical_facts) == 1
    fact = result.canonical_facts[0]
    assert fact.principal.amount == Decimal("1000")
    assert fact.contracted_amount is not None
    assert fact.contracted_amount.amount == Decimal("1500")
    assert fact.product is not None
    assert fact.product.amount == Decimal("10")
    assert fact.currency is Currency.CRC
    assert fact.contract_currency_source_code == "CONTRACT-CURRENCY-SOURCE"
    assert fact.disbursement_currency_source_code == "DISBURSEMENT-CURRENCY-SOURCE"
    assert fact.rate_type_source_code == "RATE-TYPE"
    assert fact.variable_rate_source_code == "4"
    assert fact.nominal_rate_percent == Decimal("4.25")
    assert fact.maturity_date == date(2038, 8, 13)
    assert fact.next_principal_payment_date == date(2026, 10, 20)
    assert fact.next_interest_payment_date == date(2026, 9, 20)
    assert fact.principal_payment_frequency_source_code == "12"
    assert fact.interest_payment_frequency_source_code == "4"


def test_bridge_preserves_signed_balance_and_optional_blanks() -> None:
    result = BorrowingXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(
            _fact(
                record_id="2",
                currency_code="SRC-ME",
                principal_amount=Decimal("-9186146.81"),
                contracted_amount=None,
                product_amount=None,
            )
        )
    )

    fact = result.canonical_facts[0]
    assert fact.principal.amount == Decimal("-9186146.81")
    assert fact.currency is Currency.USD
    assert fact.contracted_amount is None
    assert fact.product is None
    assert fact.product_account_code is None


def test_unmapped_currency_fails_closed_without_assuming_numeric_semantics() -> None:
    result = BorrowingXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(_fact(record_id="3", currency_code="1"))
    )

    assert not result.canonical_facts
    assert len(result.mapping_failures) == 1
    failure = result.mapping_failures[0]
    assert failure.code is IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE
    assert failure.canonical_field == "currency"
    assert "TEST-OBLIGACIONES-CURRENCY:1" in failure.message


def test_existing_mapping_failure_is_preserved_across_currency_boundary() -> None:
    failure = IRRBBSourceMappingFailure(
        source_record_id="failed",
        source_reference="XML_CONFIA:obligaciones.xml|record=failed",
        code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
        canonical_field="TipoMonedaObligacion",
        message="missing",
    )

    result = BorrowingXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(
            _fact(record_id="4", currency_code="SRC-ME"),
            failures=(failure,),
        )
    )

    assert len(result.canonical_facts) == 1
    assert result.canonical_facts[0].currency is Currency.USD
    assert result.mapping_failures == (failure,)
    assert result.source_record_count == 2


def test_catalog_rejects_duplicate_or_unevidenced_bindings() -> None:
    binding = BorrowingXMLCurrencyCodeBinding(
        source_code="SRC-MN",
        currency=Currency.CRC,
        evidence_reference="TEST:EVIDENCE:A",
    )

    with pytest.raises(ValueError, match="source codes must be unique"):
        BorrowingXMLCurrencyCatalog(
            code="TEST",
            version="1",
            evidence_reference="TEST:EVIDENCE",
            bindings=(
                binding,
                BorrowingXMLCurrencyCodeBinding(
                    source_code="SRC-MN",
                    currency=Currency.USD,
                    evidence_reference="TEST:EVIDENCE:B",
                ),
            ),
        )

    with pytest.raises(ValueError, match="evidence_reference is required"):
        BorrowingXMLCurrencyCodeBinding(
            source_code="SRC",
            currency=Currency.CRC,
            evidence_reference=" ",
        )
