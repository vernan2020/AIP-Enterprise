"""Consistent presentation-only ergonomics for real institutional pages.

All changes are Qt widget settings; no view model, source or calculation is mutated.
The function is idempotent and safe to re-apply when a previously opened page
creates new tabs or data tables on demand.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QTableView, QTableWidget, QTabWidget, QWidget


def copy_selected_table_to_tsv(table: QTableView) -> bool:
    """Copy an exact rectangular selection for spreadsheet paste, on user action.

    Never export unselected positions. Protect spreadsheet paste from text
    beginning with executable formula prefixes while retaining numeric negatives.
    """
    indexes = table.selectedIndexes()
    if not indexes:
        return False
    cells = {(index.row(), index.column()): index for index in indexes}
    row_numbers = sorted({row for row, _column in cells})
    col_numbers = sorted({column for _row, column in cells})
    lines: list[str] = []
    for row in row_numbers:
        fields: list[str] = []
        for column in col_numbers:
            index = cells.get((row, column))
            value = index.data(Qt.ItemDataRole.DisplayRole) if index is not None else ""
            field = (
                str(value if value is not None else "")
                .replace("\t", " ")
                .replace("\r", " ")
                .replace("\n", " ")
            )
            stripped = field.lstrip()
            if stripped.startswith(("=", "+", "@")) or (
                stripped.startswith("-") and stripped[1:].strip() and not _looks_numeric(stripped)
            ):
                field = "'" + field
            fields.append(field)
        lines.append("\t".join(fields))
    QGuiApplication.clipboard().setText("\n".join(lines))
    return True


def _looks_numeric(text: str) -> bool:
    try:
        float(text.replace(",", "."))
    except ValueError:
        return False
    return True


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

    tables = ([page] if isinstance(page, QTableView) else []) + page.findChildren(QTableView)
    for table in tables:
        table.setAlternatingRowColors(True)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        # Preserve per-column numeric alignment, row selection and sort policies.
        table.verticalHeader().setMinimumSectionSize(22)
        table.setShowGrid(False)
        table.horizontalHeader().setHighlightSections(False)
        # Every row can be copied directly into Excel without an intermediary
        # export file. Do not replace existing domain models or delegates.
        if not table.property("aipCopyShortcutInstalled"):
            shortcut = QShortcut(QKeySequence.StandardKey.Copy, table)
            shortcut.activated.connect(lambda target=table: copy_selected_table_to_tsv(target))
            table.setProperty("aipCopyShortcutInstalled", True)
        if isinstance(table, QTableWidget):
            for column in range(table.columnCount()):
                header = table.horizontalHeaderItem(column)
                if header is not None and not header.toolTip():
                    header.setToolTip(header.text())
