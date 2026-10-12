from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QWidget

from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import (
    MacroIntelligenceWorkspace,
)


def test_macro_dashboard_reflows_seven_existing_kpis(qt_app) -> None:
    parent = QWidget()
    grid = QGridLayout(parent)
    cards = tuple(QFrame() for _ in range(7))
    try:
        assert MacroIntelligenceWorkspace._metric_columns_for_width(600) == 2
        assert MacroIntelligenceWorkspace._metric_columns_for_width(960) == 4
        assert MacroIntelligenceWorkspace._metric_columns_for_width(1440) == 7

        for columns in (7, 4, 2, 7):
            MacroIntelligenceWorkspace._reflow_grid(grid, cards, columns)
            for index, card in enumerate(cards):
                position = grid.itemAtPosition(index // columns, index % columns)
                assert position is not None
                assert position.widget() is card
        assert len(set(map(id, cards))) == 7
    finally:
        parent.close()
        qt_app.processEvents()


def test_macro_governance_cards_can_reflow_without_replacing_values(qt_app) -> None:
    parent = QWidget()
    grid = QGridLayout(parent)
    cards = tuple(QFrame() for _ in range(4))
    try:
        cards[0].setProperty("approvedScenario", "BASE-2026-10")
        MacroIntelligenceWorkspace._reflow_grid(grid, cards, 2)
        assert grid.itemAtPosition(1, 1).widget() is cards[3]
        MacroIntelligenceWorkspace._reflow_grid(grid, cards, 4)
        assert grid.itemAtPosition(0, 3).widget() is cards[3]
        assert cards[0].property("approvedScenario") == "BASE-2026-10"
    finally:
        parent.close()
        qt_app.processEvents()
