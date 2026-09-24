from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.domain.irrbb.models import IRRBBTimeBucket, RateType
from aip.product.configured.irrbb.captaciones_capf_bucket_bridge import (
    CaptacionesCAPFPrincipalBucketBridge,
    CaptacionesCAPFPrincipalBucketFact,
)
from aip.product.configured.irrbb.captaciones_capf_contractual import CaptacionesCAPFContractualFact
from aip.product.configured.irrbb.captaciones_capf_operation_binding import (
    CaptacionesCAPFJoinedFact,
    CaptacionesCAPFOperationJoinService,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.shared.money import Currency, Money


def _xml_fact(
    *,
    operation_id: str = "CERT-346-1",
    rate_type: str = "F",
    maturity_date: date | None = date(2027, 1, 31),
) -> CaptacionesXMLCanonicalCurrencyFact:
    return CaptacionesXMLCanonicalCurrencyFact(
        source_record_id="XML_CONFIA:Pasivos_210.xml:record:1",
        source_reference="XML_CONFIA:Pasivos_210.xml|record=1",
        creditor_id="ACR-1",
        operation_id=operation_id,
        operation_type_source_code="1",
        guarantee_indicator="N",
        account_type_source_code="4",
        rate_type_source_code=rate_type,
        variable_rate_source_code=None,
        nominal_rate_percent=Decimal("7.25"),
        sugef_catalog_source_code="14",
        accounting_account_code="21312100",
        principal=Money(Decimal("1000000"), Currency.CRC),
        product_account_code="21900100",
        product=Money(Decimal("10000"), Currency.CRC),
        amount=Money(Decimal("1010000"), Currency.CRC),
        origination_date=date(2026, 1, 31),
        maturity_date=maturity_date,
        reserve_requirement_indicator="S",
        deposit_fgd_source_code="1",
    )


def _contractual_fact(
    *,
    certificate_number: str = "CERT-346-1",
    maturity_date: date = date(2027, 1, 31),
    rate_type: RateType = RateType.FIXED,
) -> CaptacionesCAPFContractualFact:
    return CaptacionesCAPFContractualFact(
        source_record_id="CAPF_XLSX:detalle.xlsx:row:2",
        source_reference="CAPF_XLSX:detalle.xlsx|sha256=abc|row=2",
        certificate_number=certificate_number,
        source_status_code="A",
        product_code="346",
        product_name="CAP GANO MÁS",
        currency_source_label="Colones",
        certificate_amount_colonized=Decimal("999999999"),
        interest_rate_percent=Decimal("7.25"),
        contractual_rate_type=rate_type,
        rate_type_rule_reference="TEST:ALL-CAP-FIXED-RATE",
        preferential_rate_percent=Decimal("0.25"),
        term_months=12,
        issue_date=date(2026, 1, 31),
        maturity_date=maturity_date,
        explicit_payment_date=None,
        interest_payment_frequency_source_label="TRIMESTRAL",
        renewal_indicator_source_code="S",
        renewal_amount_source_value=Decimal("1000000"),
        capitalizes_at_interest_payment_frequency=True,
        capitalization_frequency_source_label="TRIMESTRAL",
        product_rule_reference="TEST:product=346",
    )


def _join(
    xml_fact: CaptacionesXMLCanonicalCurrencyFact,
    facts: tuple[CaptacionesCAPFContractualFact, ...],
):
    service = CaptacionesCAPFOperationJoinService()
    return service.join(
        xml_fact=xml_fact,
        contractual_facts_by_certificate=service.index_contractual_facts(facts),
    )


@pytest.mark.parametrize(
    ("maturity", "bucket"),
    [
        (date(2026, 6, 30), IRRBBTimeBucket.DAY_1),
        (date(2026, 7, 1), IRRBBTimeBucket.DAY_1),
        (date(2026, 7, 30), IRRBBTimeBucket.DAY_1_TO_MONTH_1),
        (date(2026, 7, 31), IRRBBTimeBucket.MONTH_1_TO_3),
        (date(2046, 7, 1), IRRBBTimeBucket.OVER_YEAR_20),
    ],
)
def test_join_to_canonical_bucket_preserves_principal_and_lineage(maturity, bucket) -> None:
    joined = _join(_xml_fact(maturity_date=maturity), (_contractual_fact(maturity_date=maturity),))
    assert isinstance(joined, CaptacionesCAPFJoinedFact)
    result = CaptacionesCAPFPrincipalBucketBridge().assign(
        fact=joined, cutoff_date=date(2026, 6, 30)
    )
    assert isinstance(result, CaptacionesCAPFPrincipalBucketFact)
    assert result.assignment.bucket is bucket
    assert result.assignment.risk_date == maturity
    assert result.joined_fact is joined
    assert result.principal == joined.xml_fact.principal
    assert result.principal != joined.xml_fact.amount
    assert not result.eve_ready
    assert joined.binding_reference in result.rule_reference


@pytest.mark.parametrize("account", ["21103000", "21104000", "99900000"])
def test_non_term_accounts_remain_blocked(account: str) -> None:
    joined = _join(replace(_xml_fact(), accounting_account_code=account), (_contractual_fact(),))
    assert isinstance(joined, CaptacionesCAPFJoinedFact)
    result = CaptacionesCAPFPrincipalBucketBridge().assign(
        fact=joined, cutoff_date=date(2026, 6, 30)
    )
    assert isinstance(result, IRRBBSourceMappingFailure)
    assert result.source_record_id == joined.xml_fact.source_record_id


@pytest.mark.parametrize("cutoff", [date(2025, 12, 31), date(2027, 2, 1)])
def test_not_issued_or_matured_contract_is_not_forced_into_overnight(cutoff: date) -> None:
    joined = _join(_xml_fact(), (_contractual_fact(),))
    assert isinstance(joined, CaptacionesCAPFJoinedFact)
    result = CaptacionesCAPFPrincipalBucketBridge().assign(fact=joined, cutoff_date=cutoff)
    assert isinstance(result, IRRBBSourceMappingFailure)
