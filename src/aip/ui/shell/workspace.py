from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget, QWidget

from aip.ui.shell.page_visual_standard import apply_page_visual_standard


class Workspace(QTabWidget):
    """Tabbed workspace container for dockable views and documents."""

    def __init__(self) -> None:
        super().__init__()
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setAccessibleName("Pestañas de los módulos financieros")
        self.tabBar().setUsesScrollButtons(True)
        self.tabBar().setExpanding(False)
        self.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.currentChanged.connect(self._on_tab_activated)
        self.tabCloseRequested.connect(self._close_tab_at)
        self._pinned_tabs: set[str] = set()

    def add_tab(self, title: str, widget: QWidget) -> None:
        index = self.addTab(widget, title)
        self.tabBar().setTabToolTip(index, title)
        apply_page_visual_standard(widget)
        self.setCurrentWidget(widget)

    def open_tab(self, title: str, widget: QWidget) -> None:
        for index in range(self.count()):
            if self.tabText(index) == title:
                self.setCurrentIndex(index)
                return
        index = self.addTab(widget, title)
        self.tabBar().setTabToolTip(index, title)
        apply_page_visual_standard(widget)
        self.setCurrentWidget(widget)

    def _on_tab_activated(self, index: int) -> None:
        page = self.widget(index)
        if page is not None:
            # Newly loaded sub-tabs and tables inherit the same ergonomics.
            apply_page_visual_standard(page)

    def _close_tab_at(self, index: int) -> None:
        widget = self.widget(index)
        if widget is None:
            return
        # close() delivers closeEvent to the page (including its worker cleanup).
        # A rejected close must keep the tab and its widget alive.
        if not widget.close():
            return
        self.removeTab(index)
        widget.deleteLater()

    def close_tab(self, title: str) -> None:
        for index in range(self.count()):
            if self.tabText(index) == title:
                self._close_tab_at(index)
                return

    def pin_tab(self, title: str) -> None:
        self._pinned_tabs.add(title)

    def unpin_tab(self, title: str) -> None:
        self._pinned_tabs.discard(title)

    def is_pinned(self, title: str) -> bool:
        return title in self._pinned_tabs
