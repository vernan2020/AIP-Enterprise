from __future__ import annotations

from aip.ui.themes.palette import ThemePalette


class LightTheme:
    def stylesheet(self) -> str:
        palette = ThemePalette()
        return f"""
        QWidget {{ background-color: {palette.surface}; color: {palette.text}; }}
        QMainWindow {{ background-color: {palette.surface}; }}
        QToolBar {{ background-color: #f3f4f6; border: 1px solid {palette.border}; }}
        QLineEdit, QTextEdit, QListWidget {{ border: 1px solid {palette.border}; padding: 4px; }}
        """
