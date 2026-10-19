"""Synthetic fixtures are unit tests ONLY, never institutional runtime data."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    project_sugef210,
)
from aip.product.configured.liquidity.financial_plan_cashflow_bridge import (
    ApprovedFinancialPlanAllocation,
    build_approved_financial_plan_events,
)
from aip.product.configured.liquidity.financial_plan_source import (
    read_financial_plan_assumptions,
)

CUTOFF = date(2026, 9, 30)
MONTHS = (
    "ene-26", "feb-26", "mar-26", "abr-26", "may-26", "jun-26",
    "jul-26", "ago-26", "sept-26", "oct-26", "nov-26", "dic-26",
)
DRIVERS = (
    "Colocación bruta",
    "Gasto estimación cartera",
    "Traslado a incobrables",
    "Aportes capital social",
    "Renuncias capital social",
    "Capitalización excedentes",
    "Emisión nueva CAP (promedio)",
    "Tasa EML",
)


def _workbook(tmp_path):
    workbook = Workbook()
    matrix = workbook.active
    matrix.title = "Matriz Supuestos"
    matrix.append(["", "", "", ""])
    for _ in range(2):
        matrix.append([None])
    matrix.append(["ID", "Actividad", "Rubro", "Supuesto / Driver"])
    matrix.append([1, "Parámetros", "Tipo de cambio", "Tipo de cambio proyectado", 507.5,
                   "¢/US$", "Anual", "Parámetro", None, None, "2.1 / 7"])
    calendar = workbook.create_sheet("Calendario mensual")
    calendar.append(["Calendario mensual"])
    calendar.append([None])
    calendar.append(["Driver", *MONTHS, "Total 2026"])
    for driver in DRIVERS:
        values = [Decimal(100) if driver != "Tasa EML" else Decimal("0.09") for _ in range(12)]
        if driver == "Capitalización excedentes":
            values = [Decimal(0)] * 7 + [Decimal(100)] + [Decimal(0)] * 4
        calendar.append(
            [driver, *[float(v) for v in values],
             None if driver == "Tasa EML" else float(sum(values))]
        )
    path = tmp_path / "planning_2026.xlsx"
    workbook.save(path)
    return path


def _allocation(audit, driver="Colocación bruta", ccy="CRC", amount="1000000"):
    return ApprovedFinancialPlanAllocation(
        driver=driver, year=2026, month=10,
        payment_date=date(2026, 10, 10),
        currency=ccy, incremental_native_amount=Decimal(amount),
        overlap_crc_amount=Decimal(0),
        fx_crc_per_usd=Decimal(500) if ccy == "USD" else None,
        fx_reference="FX-APPROVAL-20260930" if ccy == "USD" else "",
        source_sha256=audit.sha256, scenario="BASE",
        assumption_id="PLAN-2026-BASE-001",
        approval_reference="ALCO-PLAN-LIQUIDEZ-001",
        plan_document_version="2026-v1",
        rationale="Explicit bank funding/liquidity allocation, fixture only",
        treasury_reconciliation_reference="TREASURY-RECON-001",
        nonduplication_reference="INCREMENTAL-2026-10-001",
        valid_from=CUTOFF, valid_to=date(2026, 12, 31),
        explicitly_approved=True,
    )


def test_real_format_year_totals_and_uncertified_future_months(tmp_path):
    audit = read_financial_plan_assumptions(_workbook(tmp_path), cutoff=CUTOFF)
    assert len(audit.parameters) == 1
    assert audit.parameters[0].source_cell == "'Matriz Supuestos'!E5"
    assert audit.eligible_cashflows == ()
    scheduled = [
        r for r in audit.monthly_inputs
        if r.driver == "Colocación bruta" and r.month == 10
    ]
    assert len(scheduled) == 1
    assert scheduled[0].reported_value == Decimal(100)
    assert scheduled[0].source_cell == "'Calendario mensual'!K4"
    assert scheduled[0].status.startswith("PENDING_APPROVAL")
    assert all(
        r.classification == "NONCASH_EXCLUDED"
        for r in audit.monthly_inputs if r.driver == "Gasto estimación cartera"
    )


def test_approved_allocations_count_asset_outflows_liability_inflows(tmp_path):
    audit = read_financial_plan_assumptions(_workbook(tmp_path), cutoff=CUTOFF)
    allocations = (
        _allocation(audit),
        replace(
            _allocation(audit),
            driver="Emisión nueva CAP (promedio)",
            currency="USD", incremental_native_amount=Decimal("2000"),
            fx_crc_per_usd=Decimal("500"), fx_reference="BANK-FX-2026",
            assumption_id="PLAN-2026-BASE-002",
            nonduplication_reference="FUNDING-NEW-202610",
        ),
    )
    approved = build_approved_financial_plan_events(
        audit=audit, cutoff=CUTOFF, scenario="BASE", allocations=allocations
    )
    assert len(approved.events) == 2
    assert approved.events[0].area == LiquidityBalanceArea.ASSET
    assert approved.events[1].area == LiquidityBalanceArea.LIABILITY
    ladder = project_sugef210(
        cutoff=CUTOFF, scenario="BASE",
        flows=approved.events, opening_liquidity={"CRC": Decimal(400000)},
        assumptions=approved.assumptions,
    )
    week = next(row for row in ladder.rows if row.window.key == "W08_14" and row.currency == "CRC")
    usd_week = next(row for row in ladder.rows if row.window.key == "W08_14" and row.currency == "USD")
    assert week.asset_outflows == Decimal(1000000)
    assert week.financing_need == Decimal(600000)
    assert usd_week.liability_inflows == Decimal(2000)
    assert usd_week.projected_liquidity is None
    assert not ladder.certified_comprehensive


def test_unapproved_or_undated_plan_is_never_booked(tmp_path):
    audit = read_financial_plan_assumptions(_workbook(tmp_path), cutoff=CUTOFF)
    with pytest.raises(ValueError, match="pending institutional approval"):
        replace(_allocation(audit), explicitly_approved=False)
    with pytest.raises(ValueError, match="not inside approved month"):
        replace(_allocation(audit), payment_date=date(2026, 11, 10))
    with pytest.raises(ValueError, match="conversion"):
        replace(_allocation(audit), currency="USD")


def test_overlap_and_non_cash_plan_do_not_flow(tmp_path):
    audit = read_financial_plan_assumptions(_workbook(tmp_path), cutoff=CUTOFF)
    with pytest.raises(ValueError, match="noncash"):
        build_approved_financial_plan_events(
            audit=audit, cutoff=CUTOFF, scenario="BASE",
            allocations=[replace(_allocation(audit), driver="Gasto estimación cartera")],
        )
    with pytest.raises(ValueError, match="overlaps contractual"):
        build_approved_financial_plan_events(
            audit=audit, cutoff=CUTOFF, scenario="BASE",
            allocations=[_allocation(audit)],
            existing_contractual_reconciliation_refs=frozenset({"INCREMENTAL-2026-10-001"}),
        )
    with pytest.raises(ValueError, match="exceed monthly"):
        build_approved_financial_plan_events(
            audit=audit, cutoff=CUTOFF, scenario="BASE",
            allocations=[replace(_allocation(audit), incremental_native_amount=Decimal("100000001"))],
        )


def test_plan_hash_and_historical_months_are_enforced(tmp_path):
    audit = read_financial_plan_assumptions(_workbook(tmp_path), cutoff=CUTOFF)
    with pytest.raises(ValueError, match="hash changed"):
        build_approved_financial_plan_events(
            audit=audit, cutoff=CUTOFF, scenario="BASE",
            allocations=[replace(_allocation(audit), source_sha256="0" * 64)],
        )
    with pytest.raises(ValueError, match="Historical"):
        build_approved_financial_plan_events(
            audit=audit, cutoff=CUTOFF, scenario="BASE",
            allocations=[replace(_allocation(audit), month=9, payment_date=date(2026, 9, 30))],
        )
