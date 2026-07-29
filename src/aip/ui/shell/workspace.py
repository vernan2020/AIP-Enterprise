from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget


class Workspace(QTabWidget):
    """Tabbed workspace container for dockable views and documents."""

    def __init__(self) -> None:
        super().__init__()
        self.setTabsClosable(True)
        self.setMovable(True)
        self._pinned_tabs: set[str] = set()

    def add_tab(self, title: str, widget: QWidget) -> None:
        self.addTab(widget, title)

    def open_tab(self, title: str, widget: QWidget) -> None:
        for index in range(self.count()):
            if self.tabText(index) == title:
                self.setCurrentIndex(index)
                return
        self.addTab(widget, title)
        self.setCurrentWidget(widget)

    def close_tab(self, title: str) -> None:
        for index in range(self.count()):
            if self.tabText(index) == title:
                self.removeTab(index)
                return

    def pin_tab(self, title: str) -> None:
        self._pinned_tabs.add(title)

    def unpin_tab(self, title: str) -> None:
        self._pinned_tabs.discard(title)

    def is_pinned(self, title: str) -> bool:
        return title in self._pinned_tabs
