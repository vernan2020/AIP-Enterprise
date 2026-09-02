from __future__ import annotations

from aip.ui.themes.palette import DarkThemePalette


class DarkTheme:
    """Tema oscuro analítico AIP Enterprise 2.0 derivado de la marca Coopealianza."""

    def stylesheet(self) -> str:
        p = DarkThemePalette()
        return f"""
        QMainWindow, QDialog {{
            background-color: {p.canvas};
            color: {p.text};
        }}
        QWidget {{
            color: {p.text};
            font-family: "Lucida Sans Unicode";
            font-size: 9.5pt;
        }}
        QToolTip {{
            background-color: #00182C;
            color: {p.text};
            border: 1px solid {p.celeste};
            padding: 5px 7px;
        }}
        QToolBar {{
            background: {p.surface};
            border: none;
            border-bottom: 1px solid {p.border};
            spacing: 1px;
            padding: 1px 4px;
        }}
        QToolBar QToolButton {{
            background: transparent;
            color: {p.text_secondary};
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            margin: 1px;
            font-weight: 600;
        }}
        QToolBar QToolButton:hover {{
            background: {p.surface_hover};
            color: {p.primary};
        }}
        QToolBar QToolButton:pressed {{
            background: {p.surface_selected};
            color: {p.primary};
        }}
        QMenuBar {{
            background: {p.surface};
            color: {p.text_secondary};
            border-bottom: 1px solid {p.border};
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 5px 9px;
        }}
        QMenuBar::item:selected {{
            background: {p.surface_hover};
            color: {p.primary};
        }}
        QMenu {{
            background: {p.surface_alt};
            color: {p.text};
            border: 1px solid {p.border_strong};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 9px;
            border-radius: 3px;
        }}
        QMenu::item:selected {{
            background: {p.surface_selected};
            color: {p.text};
        }}
        QStatusBar {{
            background: {p.surface};
            color: {p.text_secondary};
            border-top: 1px solid {p.border};
        }}
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox,
        QDateEdit, QTimeEdit, QDateTimeEdit, QComboBox {{
            background: {p.surface_alt};
            color: {p.text};
            border: 1px solid {p.border};
            border-radius: 5px;
            padding: 5px 7px;
            selection-background-color: {p.surface_selected};
            selection-color: {p.text};
        }}
        QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
        QDateEdit:hover {{
            border-color: {p.border_strong};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
        QDateEdit:focus {{
            border: 1px solid {p.celeste};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background: {p.surface_alt};
            color: {p.text};
            border: 1px solid {p.border};
            selection-background-color: {p.surface_selected};
            selection-color: {p.text};
        }}
        QPushButton {{
            background: {p.surface_alt};
            color: {p.primary};
            border: 1px solid {p.border_strong};
            border-radius: 5px;
            padding: 6px 11px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {p.surface_hover};
            border-color: {p.celeste};
        }}
        QPushButton:pressed {{
            background: {p.surface_selected};
        }}
        QPushButton:disabled {{
            color: {p.disabled};
            border-color: {p.border};
            background: {p.surface};
        }}
        QTabWidget::pane {{
            background: {p.surface};
            border: 1px solid {p.border};
            border-radius: 6px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {p.text_secondary};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 7px 13px;
            margin-right: 2px;
            font-weight: 600;
        }}
        QTabBar::tab:hover {{
            color: {p.primary};
            background: {p.surface_hover};
        }}
        QTabBar::tab:selected {{
            color: {p.primary};
            border-bottom: 2px solid {p.celeste};
            background: {p.surface};
        }}
        QTableView, QTableWidget, QTreeView, QListView, QListWidget {{
            background: {p.surface};
            alternate-background-color: {p.surface_alt};
            color: {p.text};
            border: 1px solid {p.border};
            gridline-color: {p.grid};
            selection-background-color: {p.surface_selected};
            selection-color: {p.text};
            outline: none;
        }}
        QTableView::item, QTableWidget::item, QTreeView::item, QListView::item {{
            padding: 4px 6px;
            border: none;
        }}
        QTableView::item:hover, QTableWidget::item:hover, QTreeView::item:hover,
        QListView::item:hover {{
            background: {p.surface_hover};
        }}
        QHeaderView::section {{
            background: {p.surface_alt};
            color: {p.text_secondary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            padding: 6px 7px;
            font-weight: 700;
            font-size: 9pt;
        }}
        QGroupBox {{
            background: {p.surface};
            border: 1px solid {p.border};
            border-radius: 7px;
            margin-top: 9px;
            padding-top: 7px;
            font-weight: 700;
            color: {p.primary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
        QProgressBar {{
            background: {p.surface_alt};
            border: 1px solid {p.border};
            border-radius: 4px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background: {p.mint};
            border-radius: 3px;
        }}
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 1px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border_strong};
            min-height: 30px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.celeste};
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 1px;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.border_strong};
            min-width: 30px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {p.celeste};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0px;
            height: 0px;
        }}
        QSplitter::handle {{
            background: {p.border};
        }}
        QDockWidget {{
            color: {p.text};
        }}
        QDockWidget::title {{
            background: {p.surface_alt};
            color: {p.primary};
            border-bottom: 1px solid {p.border};
            padding: 6px;
            font-weight: 700;
        }}
        """
