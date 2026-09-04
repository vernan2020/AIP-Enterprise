from __future__ import annotations

import importlib
import os

from PySide6.QtWidgets import QApplication, QLabel

import aip.main
from aip.ui.application import app as application_app_module
from aip.ui.main_window import MainWindow as LegacyMainWindow
from aip.ui.shell.main_window import MainWindow as RC1MainWindow


def test_production_entry_point_uses_rc1_shell(monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    captured: dict[str, object] = {}

    class RecordingApplication(application_app_module.AIPApplication):
        def create_window(self):
            window = super().create_window()
            captured["window"] = window
            return window

        def exec(self) -> int:
            return 0

    application_main_module = importlib.import_module("aip.ui.application.main")
    monkeypatch.setattr(application_main_module, "AIPApplication", RecordingApplication)

    exit_code = aip.main.main(["aip-enterprise"])

    assert exit_code == 0
    window = captured["window"]
    assert isinstance(window, RC1MainWindow)
    assert not isinstance(window, LegacyMainWindow)
    assert "AIP Enterprise 1.0.0 RC1" in window.windowTitle()
    assert any("MODO DEMO" in label.text().upper() for label in window.findChildren(QLabel))
