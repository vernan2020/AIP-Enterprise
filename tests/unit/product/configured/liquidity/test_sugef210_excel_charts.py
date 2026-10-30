"""Regression for native-currency charts that never turn missing sources into zero."""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from openpyxl import Workbook, load_workbook

from aip.product.configured.liquidity.sugef210_excel_charts import (
    add_partial_cashflow_charts,
)


def _projection(*, has_events: bool = True) -> Any:
    first = SimpleNamespace(key="D0", label="Día 0")
    second = SimpleNamespace(key="D1", label="Día 1")
    return SimpleNamespace(
        windows=(first, second),
        rows=(
            SimpleNamespace(
                currency="CRC",
                window=first,
                net_flow=Decimal("125.50"),
                accumulated_flow=Decimal("125.50"),
                event_count=1 if has_events else 0,
            ),
            SimpleNamespace(
                currency="USD",
                window=first,
                net_flow=Decimal("0"),
                accumulated_flow=Decimal("0"),
                event_count=0,
            ),
            SimpleNamespace(
                currency="CRC",
                window=second,
                net_flow=Decimal("0"),
                accumulated_flow=Decimal("125.50" if has_events else "0"),
                event_count=0,
            ),
            SimpleNamespace(
                currency="USD",
                window=second,
                net_flow=Decimal("0"),
                accumulated_flow=Decimal("0"),
                event_count=0,
            ),
        ),
        source_flow_count=1 if has_events else 0,
    )


def test_partial_excel_charts_preserve_nd_and_native_currency(tmp_path) -> None:
    workbook = Workbook()
    add_partial_cashflow_charts(workbook, _projection())
    sheet = workbook["Gráficos parciales"]
    assert "PARCIAL NO CERTIFICADA" in sheet["A1"].value
    assert sheet["A5"].value == "Día 0"
    assert sheet["B5"].value == Decimal("125.50")
    assert sheet["C5"].value == Decimal("125.50")
    assert sheet["D5"].value == "N/D"
    assert sheet["E5"].value == Decimal("0")
    assert sheet["B6"].value == "N/D"
    assert sheet["C6"].value == Decimal("125.50")
    assert len(sheet._charts) == 2  # Only approved CRC receipts; no USD chart.
    output = tmp_path / "partial_native_currency.xlsx"
    workbook.save(output)
    reopened = load_workbook(output)
    assert reopened["Gráficos parciales"]["D5"].value == "N/D"
    assert len(reopened["Gráficos parciales"]._charts) == 2


def test_no_evidence_generates_no_charts_or_numeric_zeros() -> None:
    workbook = Workbook()
    add_partial_cashflow_charts(workbook, _projection(has_events=False))
    sheet = workbook["Gráficos parciales"]
    assert sheet["B5"].value == "N/D"
    assert sheet["C5"].value == "N/D"
    assert sheet["D5"].value == "N/D"
    assert sheet["E5"].value == "N/D"
    assert not sheet._charts
    assert "Sin eventos" in sheet["A24"].value


def test_incomplete_projection_is_rejected_before_charting() -> None:
    projection = _projection()
    projection.rows = projection.rows[:-1]
    with pytest.raises(ValueError, match="incomplete CRC/USD"):
        add_partial_cashflow_charts(Workbook(), projection)
