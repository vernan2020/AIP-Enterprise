"""Regression: portfolio uses a compact real-data explorer, not empty placeholders."""

from __future__ import annotations

import csv

from PySide6.QtWidgets import QFileDialog, QScrollArea

from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.modules.portfolio.widgets.portfolio_filter_panel import PortfolioFilterPanel


def _position(isin: str, issuer: str, currency: str, instrument: str) -> PortfolioRow:
    return PortfolioRow(
        isin=isin,
        issuer=issuer,
        instrument=instrument,
        currency=currency,
        nominal="1500000",
        market_value="1450000",
        book_value="1400000",
        yield_value="6.25%",
        modified_duration="2.35",
        classification="D.V",
        hqla_status="Elegible",
        mil_status="Elegible",
        recommendation="Mantener",
    )


def test_portfolio_filters_populate_from_institutional_rows_not_sample_issuer(qt_app) -> None:
    filters = PortfolioFilterPanel()
    try:
        assert filters.issuer.count() == 1
        assert filters.issuer.findText("Banco Acme") == -1
        rows = (
            _position("CR001", "Gobierno", "CRC", "TP"),
            _position("BC001", "BCCR", "CRC", "CDP"),
            _position("US001", "Banco Estatal", "USD", "Bono"),
        )
        filters.set_rows(rows)
        assert filters.issuer.count() == 4
        assert filters.currency.count() == 3
        filters.issuer.setCurrentText("BCCR")
        assert filters.matches(rows[1])
        assert not filters.matches(rows[0])
        filters.reset_filters()
        assert all(filters.matches(row) for row in rows)
    finally:
        filters.close()


def test_portfolio_position_table_is_full_height_and_search_updates_inspector(qt_app) -> None:
    view = PortfolioView()
    try:
        rows = (
            _position("CR001", "Gobierno", "CRC", "TP"),
            _position("BC001", "BCCR", "CRC", "CDP"),
            _position("US001", "Banco Estatal", "USD", "Bono"),
        )
        view._positions.bind_rows(rows)
        view._filter_panel.set_rows(rows)
        view._tabs.setCurrentIndex(3)
        view.resize(1350, 850)
        view.show()
        qt_app.processEvents()
        assert not isinstance(view.layout().itemAt(0).widget(), QScrollArea)
        assert view._tabs.height() > 400
        assert view._positions._table.height() > 200
        assert view._filter_panel.sizeHint().height() < 205
        view._filter_panel.search.setText("BC001")
        qt_app.processEvents()
        assert view._positions._count_label.text() == "1 de 3 posiciones"
        assert [r.isin for r in view._positions.visible_rows()] == ["BC001"]
        assert view._details._values["issuer"].text() == "BCCR"
        view._toolbar.reset_action.trigger()
        qt_app.processEvents()
        assert len(view._positions.visible_rows()) == 3
        assert view._positions._table.isSortingEnabled()
    finally:
        view.close()
        qt_app.processEvents()


def test_portfolio_export_respects_filtered_positions(qt_app, monkeypatch, tmp_path) -> None:
    view = PortfolioView()
    path = tmp_path / "posiciones.csv"
    try:
        rows = (
            _position("CR001", "Gobierno", "CRC", "TP"),
            _position("BC001", "BCCR", "CRC", "CDP"),
        )
        view._positions.bind_rows(rows)
        view._filter_panel.set_rows(rows)
        view._filter_panel.search.setText("BC001")
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "CSV"))
        view._toolbar.export_action.trigger()
        with path.open(encoding="utf-8-sig", newline="") as inp:
            data = list(csv.reader(inp))
        assert len(data) == 2
        assert data[1][0] == "BC001"
        assert data[1][1] == "BCCR"
        assert "Gobierno" not in data[1]
    finally:
        view.close()
        qt_app.processEvents()


def test_refresh_preserves_real_position_widgets_and_splitter(qt_app) -> None:
    view = PortfolioView()
    try:
        original_positions = view._positions
        original_splitter = view._content_splitter
        view.bind_view_model(view.view_model())
        assert view._positions is original_positions
        assert view._content_splitter is original_splitter
    finally:
        view.close()
        qt_app.processEvents()
