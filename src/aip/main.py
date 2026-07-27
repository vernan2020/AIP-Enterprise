from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from aip.application.kernel import ApplicationKernel
from aip.core.bootstrap import Bootstrap
from aip.core.paths import ProjectPaths
from aip.core.version import APP_NAME, APP_VERSION


def main() -> int:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setApplicationVersion(APP_VERSION)

    paths = ProjectPaths.discover()
    services = Bootstrap(paths).initialize()
    kernel = ApplicationKernel(qt_application=qt_app, services=services)
    return kernel.run()
