"""Source-certified Master principal inclusion; test fixtures are not operational data."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.liquidity.sugef210_approved_master_principal import (
    ApprovedMasterPrincipalPosition,
    admit_approved_master_principal,
)
from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    MasterPrincipalEvidence,
)

CUTOFF = date(2026, 9, 30)
HASH = "c" * 64


def _master() -> MasterPrincipalEvidence:
    events = tuple(
        LiquidityProjectionFlow(
            reference=f"MASTER:{HASH}:ROW-{number}:PRINCIPAL",
            source=f"INSTITUTIONAL_MASTER_SHA256:{HASH}",
            currency="CRC" if number == 1 else "USD",
            payment_date=CUTOFF + timedelta(days=day),
            amount=Decimal(amount),
            side=LiquidityFlowSide.INFLOW,
            area=LiquidityBalanceArea.ASSET,
            evidence=LiquidityEvidence.CONTRACTUAL,
        )
        for number, day, amount in ((1, 31, "120"), (2, 90, "45"))
    )
    return MasterPrincipalEvidence(
        cutoff=CUTOFF,
        master_sha256=HASH,
        positions_read=2,
        flows=events,
        excluded=(),
        principal_by_currency=(("CRC", Decimal("120")), ("USD", Decimal("45"))),
    )


def _approve(flow: LiquidityProjectionFlow) -> ApprovedMasterPrincipalPosition:
    return ApprovedMasterPrincipalPosition(
        cashflow_reference=flow.reference,
        payment_date=flow.payment_date,
        original_principal=flow.amount,
        currency=flow.currency,
        approval_reference="TEST-TREASURY-SETTLEMENT",
        settlement_availability_reference="TEST-CUSTODIAN-SETTLEMENT",
        restriction_clearance_reference="TEST-UNRESTRICTED",
        nonduplication_reference="TEST-ROW-NONDUP-" + flow.reference,
    )


def test_only_individually_approved_master_rows_enter_ladder():
    source = _master()
    approved = admit_approved_master_principal(
        source=source,
        cutoff=CUTOFF,
        expected_master_sha256=HASH,
        records=(_approve(source.flows[0]),),
    )
    assert len(approved.flows) == 1
    assert approved.flows[0].amount == Decimal("120")
    assert dict(approved.principal_by_currency) == {"CRC": Decimal("120"), "USD": Decimal("0")}
    assert approved.positions_read == len(approved.flows) + len(approved.excluded)
    assert approved.excluded[0].reason == "NOT_INDIVIDUALLY_APPROVED_FOR_LIQUIDITY"


def test_amount_maturity_currency_and_source_hash_cannot_be_substituted():
    source = _master()
    approval = _approve(source.flows[0])
    for variant in (
        replace(approval, original_principal=Decimal("121")),
        replace(approval, payment_date=approval.payment_date + timedelta(days=1)),
        replace(approval, currency="USD"),
    ):
        with pytest.raises(ValueError, match="differs from source"):
            admit_approved_master_principal(
                source=source,
                cutoff=CUTOFF,
                expected_master_sha256=HASH,
                records=(variant,),
            )
    with pytest.raises(ValueError, match="hash"):
        admit_approved_master_principal(
            source=source,
            cutoff=CUTOFF,
            expected_master_sha256="0" * 64,
            records=(approval,),
        )


def test_duplicate_principal_and_unapproved_source_record_blocked():
    source = _master()
    approval = _approve(source.flows[0])
    with pytest.raises(ValueError, match="repeated"):
        admit_approved_master_principal(
            source=source,
            cutoff=CUTOFF,
            expected_master_sha256=HASH,
            records=(approval, approval),
        )
    with pytest.raises(ValueError, match="not in original Master"):
        admit_approved_master_principal(
            source=source,
            cutoff=CUTOFF,
            expected_master_sha256=HASH,
            records=(replace(approval, cashflow_reference="UNKNOWN"),),
        )
