from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QComboBox, QSplitter, QTabWidget, QWidget

from aip.ui.modules.market.views.market_view import MarketView
from aip.ui.modules.market.views.relative_value_view import RelativeValueView


def test_market_view_renders_and_binds(qt_app) -> None:
    view = MarketView()

    assert isinstance(view, QWidget)
    assert view.view_model().status == "loaded"
    assert view.findChild(QSplitter, "marketAnalyticalSplitter") is not None

    tabs = view.findChild(QTabWidget, "marketRelativeValueTabs")
    assert tabs is not None
    assert tabs.count() == 3
    assert tabs.tabText(0).startswith("RV Portafolio")
    assert tabs.tabText(1).startswith("RV Mercado")
    assert tabs.tabText(2).startswith("Rotación")


def test_relative_value_filter_exposes_compra_venta_without_legacy_labels(qt_app) -> None:
    view = MarketView()

    classification_filter = view.findChild(
        QComboBox,
        "marketRelativeValueClassificationFilter",
    )
    assert classification_filter is not None

    visible_labels = [
        classification_filter.itemText(index) for index in range(classification_filter.count())
    ]
    assert visible_labels == ["TODAS", "COMPRA", "NEUTRAL", "VENTA"]
    assert "BARATO" not in visible_labels
    assert "CARO" not in visible_labels

    assert classification_filter.itemData(1) == "BARATO"
    assert classification_filter.itemData(3) == "CARO"


def test_relative_value_table_maps_legacy_classifications_to_compra_venta(qt_app) -> None:
    rows = (
        SimpleNamespace(
            series="SERIE-COMPRA",
            currency="CRC",
            classification="BARATO",
            spread_bp=25.0,
            market_yield=6.5,
            curve_yield=6.25,
            tenor=2.0,
            market_value_crc=1_000_000.0,
            position_count=1,
        ),
        SimpleNamespace(
            series="SERIE-VENTA",
            currency="CRC",
            classification="CARO",
            spread_bp=-25.0,
            market_yield=6.0,
            curve_yield=6.25,
            tenor=2.0,
            market_value_crc=1_000_000.0,
            position_count=1,
        ),
    )

    view = RelativeValueView(rows)
    table = view.table()

    assert table.item(0, 2).text() == "COMPRA"
    assert table.item(1, 2).text() == "VENTA"
    assert {table.item(row, 2).text() for row in range(table.rowCount())}.isdisjoint(
        {"BARATO", "CARO"}
    )
