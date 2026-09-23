from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import (
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.product.configured.irrbb.captaciones_xml_batch_bridge import (
    CaptacionesXMLNormalizationBatchResult,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCurrencyBridge,
)
from aip.product.configured.irrbb.captaciones_xml_currency_catalog import (
    CaptacionesXMLCurrencyCatalog,
    CaptacionesXMLCurrencyCodeBinding,
)
from aip.product.configured.irrbb.captaciones_xml_normalizer import CaptacionesXMLFact
from aip.shared.money import Currency


def _catalog() -> CaptacionesXMLCurrencyCatalog:
    return CaptacionesXMLCurrencyCatalog(
        code="TEST-CAPTACIONES-CURRENCY",
        version="1",
        evidence_reference="TEST:EVIDENCE:CATALOG",
        bindings=(
            CaptacionesXMLCurrencyCodeBinding(
                source_code="SRC-MN",
                currency=Currency.CRC,
                evidence_reference="TEST:EVIDENCE:SRC-MN",
            ),
            CaptacionesXMLCurrencyCodeBinding(
                source_code="SRC-ME",
                currency=Currency.USD,
                evidence_reference="TEST:EVIDENCE:SRC-ME",
            ),
        ),
    )


def _fact(*, record_id: str, currency_code: str) -> CaptacionesXMLFact:
    return CaptacionesXMLFact(
        source_record_id=f"XML_CONFIA:captaciones.xml:record:{record_id}",
        source_reference=f"XML_CONFIA:captaciones.xml|record={record_id}",
        creditor_id="ACREEDOR",
        operation_id=f"OP-{record_id}",
        operation_type_source_code="OP-TYPE",
        guarantee_indicator=None,
        currency_source_code=currency_code,
        rate_type_source_code="RATE-TYPE",
        variable_rate_source_code=None,
        nominal_rate_percent=None,
        sugef_catalog_source_code=None,
        accounting_account_code="21103100",
        principal_amount=Decimal("1000"),
        product_account_code=None,
        product_amount=Decimal("10"),
        origination_date=date(2025, 1, 1),
        maturity_date=date(2027, 1, 1),
        reserve_requirement_indicator=None,
        account_type_source_code="ACCOUNT-TYPE",
        deposit_fgd_source_code=None,
    )


def _batch(
    *facts: CaptacionesXMLFact,
    failures: tuple[IRRBBSourceMappingFailure, ...] = (),
) -> CaptacionesXMLNormalizationBatchResult:
    return CaptacionesXMLNormalizationBatchResult(
        cutoff_date=date(2026, 8, 31),
        source_file_name="Pasivos_Cuentas_Contables_210.xml",
        source_sha256="a" * 64,
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

    with pytest.raises(KeyError, match="unmapped Captaciones XML currency source code: 1"):
        catalog.resolve("1")

    with pytest.raises(KeyError, match="unmapped Captaciones XML currency source code: 2"):
        catalog.resolve("2")


def test_bridge_maps_total_balance_to_money_without_product_classification() -> None:
    result = CaptacionesXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(_fact(record_id="1", currency_code="SRC-MN"))
    )

    assert not result.mapping_failures
    assert len(result.canonical_facts) == 1
    fact = result.canonical_facts[0]
    assert fact.amount.amount == Decimal("1010")
    assert fact.currency is Currency.CRC
    assert fact.account_type_source_code == "ACCOUNT-TYPE"
    assert fact.operation_type_source_code == "OP-TYPE"
    assert fact.rate_type_source_code == "RATE-TYPE"


def test_unmapped_currency_fails_closed_without_assuming_numeric_semantics() -> None:
    result = CaptacionesXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(_fact(record_id="2", currency_code="1"))
    )

    assert not result.canonical_facts
    assert len(result.mapping_failures) == 1
    failure = result.mapping_failures[0]
    assert failure.code is IRRBBSourceMappingFailureCode.UNSUPPORTED_SOURCE_VALUE
    assert failure.canonical_field == "currency"
    assert "TEST-CAPTACIONES-CURRENCY:1" in failure.message


def test_existing_mapping_failure_is_preserved_across_currency_boundary() -> None:
    failure = IRRBBSourceMappingFailure(
        source_record_id="failed",
        source_reference="XML_CONFIA:captaciones.xml|record=failed",
        code=IRRBBSourceMappingFailureCode.MISSING_REQUIRED_CANONICAL_FIELD,
        canonical_field="TipoCuenta",
        message="missing",
    )

    result = CaptacionesXMLCurrencyBridge(catalog=_catalog()).map_batch(
        _batch(
            _fact(record_id="3", currency_code="SRC-ME"),
            failures=(failure,),
        )
    )

    assert len(result.canonical_facts) == 1
    assert result.canonical_facts[0].currency is Currency.USD
    assert result.mapping_failures == (failure,)
    assert result.source_record_count == 2


def test_catalog_rejects_duplicate_or_unevidenced_bindings() -> None:
    binding = CaptacionesXMLCurrencyCodeBinding(
        source_code="SRC-MN",
        currency=Currency.CRC,
        evidence_reference="TEST:EVIDENCE:A",
    )

    with pytest.raises(ValueError, match="source codes must be unique"):
        CaptacionesXMLCurrencyCatalog(
            code="TEST",
            version="1",
            evidence_reference="TEST:EVIDENCE",
            bindings=(
                binding,
                CaptacionesXMLCurrencyCodeBinding(
                    source_code="SRC-MN",
                    currency=Currency.USD,
                    evidence_reference="TEST:EVIDENCE:B",
                ),
            ),
        )

    with pytest.raises(ValueError, match="evidence_reference is required"):
        CaptacionesXMLCurrencyCodeBinding(
            source_code="SRC",
            currency=Currency.CRC,
            evidence_reference=" ",
        )
