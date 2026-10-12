from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
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


@pytest.fixture(autouse=True)
def close_orphan_qt_windows(qt_app: QApplication) -> Iterator[None]:
    """End each UI test with its own QWidget lifetime, not a late GC cycle.

    Several legacy UI tests construct top-level windows without closing them.
    Their signal/slot reference cycles leave native QObjects pending until
    pytest/coverage forces garbage collection after the *entire* unit suite.
    Keep existing windows intact; only reclaim those created by this test.
    All tests and coverage checks remain enabled.
    """
    existing = set(QApplication.topLevelWidgets())
    try:
        yield
    finally:
        for widget in QApplication.topLevelWidgets():
            if widget not in existing:
                widget.close()  # Close child workers via the production closeEvent.
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt_app.processEvents()
