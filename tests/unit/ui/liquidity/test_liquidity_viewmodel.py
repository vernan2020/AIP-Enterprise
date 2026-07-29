from __future__ import annotations

from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel


def test_view_model_is_immutable_and_serializable() -> None:
    row = LiquidityRow(
        section="cashflow",
        label="Inflows",
        value="100.00",
        bucket="T+0",
        status="Healthy",
        policy_reference="POL-1",
        calculation_id="calc-1",
        correlation_id="corr-1",
    )
    view_model = LiquidityViewModel(
        summary=type("Summary", (), {"liquidity_date": "2026-07-29", "cash_position": "100.00", "net_cash_flow": "10.00", "liquidity_gap": "0.00", "hqla_capacity": "80.00", "mil_eligible_capacity": "60.00", "stress_result": "Stable", "policy_status": "Compliant"})(),
        cashflow_rows=(row,),
        gap_rows=(),
        hqla_rows=(),
        mil_rows=(),
        stress_rows=(),
        filters={"currency": "USD"},
        selected_section="cashflow",
        theme="light",
        status="loaded",
        warnings=("synced",),
        calculation_id="calc-1",
        correlation_id="corr-1",
    )

    dumped = view_model.to_dict()

    assert view_model.filters["currency"] == "USD"
    assert dumped["selected_section"] == "cashflow"
    assert dumped["cashflow_rows"][0]["bucket"] == "T+0"
