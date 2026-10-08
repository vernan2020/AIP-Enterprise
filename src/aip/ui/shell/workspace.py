from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget


class Workspace(QTabWidget):
    """Tabbed workspace container for dockable views and documents."""

    def __init__(self) -> None:
        super().__init__()
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self._close_tab_at)
        self._pinned_tabs: set[str] = set()

    def add_tab(self, title: str, widget: QWidget) -> None:
        self.addTab(widget, title)
        self.setCurrentWidget(widget)

    def open_tab(self, title: str, widget: QWidget) -> None:
        for index in range(self.count()):
            if self.tabText(index) == title:
                self.setCurrentIndex(index)
                return
        self.addTab(widget, title)
        self.setCurrentWidget(widget)

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
