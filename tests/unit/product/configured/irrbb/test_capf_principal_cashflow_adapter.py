from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.irrbb.models import BankingBookSide, CashFlowAmountStatus, RateType
from aip.product.configured.irrbb.capf_principal_cashflow_adapter import (
    adapt_capf_principal,
)
from aip.product.configured.irrbb.captaciones_capf_bucket_batch import (
    CaptacionesCAPFPrincipalBucketBatchBridge,
)
from aip.product.configured.irrbb.captaciones_capf_contractual import (
    CaptacionesCAPFContractualFact,
)
from aip.product.configured.irrbb.captaciones_capf_operation_binding import (
    CaptacionesCAPFJoinedFact,
    CaptacionesCAPFOperationJoinService,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
)
from aip.product.configured.irrbb.contractual_cashflow_19band import (
    Contractual19BandEvidenceAggregator,
)
from aip.shared.money import Currency, Money


def _joined() -> CaptacionesCAPFJoinedFact:
    operation = "CERT-001"
    xml_fact = CaptacionesXMLCanonicalCurrencyFact(
        source_record_id="Pasivos210:row:7",
        source_reference="XML_CONFIA:Pasivos_210.xml|row=7",
        creditor_id="ACREEDOR-001",
        operation_id=operation,
        operation_type_source_code="1",
        guarantee_indicator="N",
        account_type_source_code="4",
        rate_type_source_code="F",
        variable_rate_source_code=None,
        nominal_rate_percent=Decimal("7.25"),
        sugef_catalog_source_code="14",
        accounting_account_code="21312100",
        principal=Money(Decimal("1234.56"), Currency.CRC),
        product_account_code="21900100",
        product=Money(Decimal("100"), Currency.CRC),
        amount=Money(Decimal("1334.56"), Currency.CRC),
        origination_date=date(2026, 1, 1),
        maturity_date=date(2026, 12, 31),
        reserve_requirement_indicator="S",
        deposit_fgd_source_code="1",
    )
    contract = CaptacionesCAPFContractualFact(
        source_record_id="CAPF:row:5",
        source_reference="CAPF_XLSX:certificados.xlsx|row=5",
        certificate_number=operation,
        source_status_code="A",
        product_code="346",
        product_name="CAP GANO MAS",
        currency_source_label="Colones",
        certificate_amount_colonized=Decimal("999999999"),
        interest_rate_percent=Decimal("7.25"),
        contractual_rate_type=RateType.FIXED,
        rate_type_rule_reference="CERTIFIED-FIXED",
        preferential_rate_percent=None,
        term_months=12,
        issue_date=date(2026, 1, 1),
        maturity_date=date(2026, 12, 31),
        explicit_payment_date=None,
        interest_payment_frequency_source_label="TRIMESTRAL",
        renewal_indicator_source_code="N",
        renewal_amount_source_value=None,
        capitalizes_at_interest_payment_frequency=True,
        capitalization_frequency_source_label="TRIMESTRAL",
        product_rule_reference="CAPF-346",
    )
    joined = CaptacionesCAPFOperationJoinService().join(
        xml_fact=xml_fact,
        contractual_facts_by_certificate={operation: contract},
    )
    assert isinstance(joined, CaptacionesCAPFJoinedFact)
    return joined


def test_adapter_uses_xml_principal_not_xlsx_amount_or_accrued_product() -> None:
    cutoff = date(2026, 9, 30)
    batch = CaptacionesCAPFPrincipalBucketBatchBridge().build(
        cutoff_date=cutoff, joined_facts=(_joined(),)
    )
    result = adapt_capf_principal(batch)
    assert result.source_record_count == 1
    assert result.converted_principal_count == 1
    assert result.failed_record_count == 0
    assert not result.publishable_regulatory_gap
    event = result.flows[0].cashflow
    assert event.position_id == "CERT-001"
    assert event.side is BankingBookSide.LIABILITY
    assert event.amount == Money(Decimal("1234.56"), Currency.CRC)
    assert event.amount_status is CashFlowAmountStatus.SOURCE_PROVIDED
    assert event.cashflow_date == date(2026, 12, 31)
    assert "XML_CONFIA" in event.source_reference
    assert "CAPF_XLSX" in event.source_reference
    assert "CAPF_FIXED_PRINCIPAL_MATURITY" in result.flows[0].validation_reference

    bucketed = Contractual19BandEvidenceAggregator().aggregate(
        cutoff_date=cutoff, flows=result.flows
    )
    assert bucketed.total_flows == 1
    assert len(bucketed.rows) == 19
    assert bucketed.included_segments == ("CAPTACIONES",)
    assert bucketed.missing_segments == ("BORROWING", "CREDIT", "INVESTMENT")
    assert sum(row.liabilities for row in bucketed.rows) == Decimal("1234.56")
    assert sum(row.assets for row in bucketed.rows) == 0
    assert not bucketed.publishable_regulatory_gap
