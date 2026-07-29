from __future__ import annotations

from aip.ui.themes.palette import ThemePalette


class DarkTheme:
    def stylesheet(self) -> str:
        palette = ThemePalette()
        return f"""
        QWidget {{ background-color: #111827; color: #f9fafb; }}
        QMainWindow {{ background-color: #111827; }}
        QToolBar {{ background-color: #1f2937; border: 1px solid {palette.border}; }}
        QLineEdit, QTextEdit, QListWidget {{ background-color: #1f2937; border: 1px solid {palette.border}; padding: 4px; }}
        """
