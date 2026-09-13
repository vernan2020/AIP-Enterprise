from __future__ import annotations

from aip.ui.dialogs.about_dialog import AboutDialog
from aip.ui.dialogs.exception_dialog import ExceptionDialog
from aip.ui.dialogs.settings_dialog import SettingsDialog


def test_dialogs_construct(qt_app) -> None:
    about = AboutDialog()
    assert about.windowTitle() == "Acerca de AIP Enterprise"

    exception_dialog = ExceptionDialog(RuntimeError("boom"))
    assert exception_dialog.windowTitle() == "Unexpected Error"

    settings = SettingsDialog()
    assert settings.windowTitle() == "Settings"
