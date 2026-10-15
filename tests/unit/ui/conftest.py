from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QT_APP: QApplication | None = None


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Keep QApplication alive throughout Qt tests and drain widgets before exit.

    Qt shared objects must outlive child widgets and pending Qt events. A strong
    module-level reference protects the QApplication wrapper against GC; the
    session teardown disposes test windows while the application still exists.
    """

    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    yield app

    # Allow asynchronous presentation callbacks to reach the UI thread before
    # closing surviving test windows. Do not destroy the application here.
    app.processEvents()
    pool = QThreadPool.globalInstance()
    if not pool.waitForDone(15000):
        pytest.fail("Qt worker tasks did not finish before UI test teardown")
    app.processEvents()
    for window in list(app.topLevelWidgets()):
        window.close()
        window.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
