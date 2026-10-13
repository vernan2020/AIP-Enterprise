"""Consistent presentation-only ergonomics for real institutional pages.

All changes are Qt widget settings; no view model, source or calculation is mutated.
The function is idempotent and safe to re-apply when a previously opened page
creates new tabs or data tables on demand.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableView, QTabWidget, QWidget


def apply_page_visual_standard(page: QWidget) -> None:
    """Improve tabs and dense tables without changing sort or selection semantics."""
    tabs = ([page] if isinstance(page, QTabWidget) else []) + page.findChildren(QTabWidget)
    for widget in tabs:
        tab_bar = widget.tabBar()
        tab_bar.setUsesScrollButtons(True)
        tab_bar.setExpanding(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        for index in range(widget.count()):
            tab_bar.setTabToolTip(index, widget.tabText(index))

    tables = ([page] if isinstance(page, QTableView) else []) + page.findChildren(
        QTableView
    )
    for table in tables:
        table.setAlternatingRowColors(True)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        # Preserve per-column numeric alignment, row selection and sort policies.
        table.verticalHeader().setMinimumSectionSize(22)
