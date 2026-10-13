"""Presentation contracts that apply across all AIP Enterprise modules."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTabWidget, QVBoxLayout, QWidget

from aip.ui.modules.executive.widgets.executive_metric_card import ExecutiveMetricCard
from aip.ui.shell.page_visual_standard import apply_page_visual_standard
from aip.ui.shell.ribbon import Ribbon
from aip.ui.shell.workspace import Workspace
from aip.ui.themes.dark_theme import DarkTheme
from aip.ui.themes.light_theme import LightTheme


def test_page_standard_keeps_table_semantics_and_improves_legibility(qt_app) -> None:
    root = QWidget()
    layout = QVBoxLayout(root)
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Indicadores de rentabilidad y suficiencia patrimonial")
    table = QTableWidget(2, 3)
    table.setSortingEnabled(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    layout.addWidget(tabs)
    layout.addWidget(table)
    try:
        apply_page_visual_standard(root)
        apply_page_visual_standard(root)
        assert tabs.tabBar().usesScrollButtons()
        assert not tabs.tabBar().expanding()
        assert tabs.tabBar().elideMode() == Qt.TextElideMode.ElideRight
        assert tabs.tabBar().tabToolTip(0) == tabs.tabText(0)
        assert table.alternatingRowColors()
        assert table.textElideMode() == Qt.TextElideMode.ElideRight
        assert table.horizontalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
        assert table.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
        assert table.isSortingEnabled()
        assert table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectItems
    finally:
        root.close()


def test_ribbon_overflow_keeps_all_destinations_callable(qt_app) -> None:
    ribbon = Ribbon()
    try:
        ribbon.resize(680, 58)
        ribbon._update_overflow()
        assert ribbon._overflow_button.isVisibleTo(ribbon)
        assert not ribbon.action("Inteligencia Macroeconómica").isVisible()
        more = ribbon._overflow_actions["Inteligencia Macroeconómica"]
        assert more.isVisible()
        calls: list[bool] = []
        ribbon.action("Inteligencia Macroeconómica").triggered.connect(
            lambda _checked=False: calls.append(True)
        )
        more.trigger()
        assert calls == [True]
        ribbon.resize(2500, 58)
        ribbon._update_overflow()
        assert all(action.isVisible() for action in ribbon._actions.values())
        assert ribbon._overflow_button.isHidden()
    finally:
        ribbon.close()


def test_workspace_preserves_full_tab_titles_and_scroll_navigation(qt_app) -> None:
    workspace = Workspace()
    try:
        for title in (
            "Inteligencia Macroeconómica",
            "Riesgo de Tasas · RTILB",
            "Análisis Financiero",
        ):
            workspace.add_tab(title, QWidget())
        assert workspace.tabBar().usesScrollButtons()
        assert workspace.tabBar().elideMode() == Qt.TextElideMode.ElideRight
        assert workspace.tabBar().tabToolTip(0) == "Inteligencia Macroeconómica"
        assert workspace.tabBar().tabToolTip(2) == "Análisis Financiero"
    finally:
        workspace.close()


def test_executive_metric_card_has_selectable_large_value(qt_app) -> None:
    card = ExecutiveMetricCard("Suficiencia patrimonial", "20.05%")
    try:
        assert card.minimumHeight() >= 104
        assert card.accessibleName() == "Suficiencia patrimonial"
        value = card.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)[1]
        assert value.text() == "20.05%"
        assert value.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
        assert "color:#FFFFFF" in value.styleSheet()
    finally:
        card.close()


def test_institutional_global_styles_apply_to_all_financial_pages() -> None:
    for theme in (LightTheme(), DarkTheme()):
        css = theme.stylesheet()
        assert "font-size: 10pt;" in css
        assert "QTableView::item:selected" in css
        assert "QHeaderView::section:hover" in css
