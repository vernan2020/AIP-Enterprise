from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QT_APP: QApplication | None = None


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Keep one strong QApplication reference for the complete pytest process.

    PySide6 may abort during interpreter teardown when the session fixture owns
    the last Python wrapper for Qt's shared application objects. Keeping the
    application module-global avoids fixture finalization deleting those shared
    QObjects after the tests have already passed.
    """

    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app
