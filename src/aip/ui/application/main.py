from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from aip.core.startup_timing import StartupTimer
from aip.core.version import APP_NAME, APP_VERSION
from aip.product.demo.bootstrap.demo_bootstrap import DemoBootstrap
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.ui.application.app import AIPApplication
from aip.ui.services.diagnostic_service import DiagnosticMetricsStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    startup_timer: StartupTimer | None = None,
) -> int:
    """Canonical entry point for the desktop application."""

    timer = startup_timer or StartupTimer()

    with timer.stage("argument_parsing"):
        raw_args = list(argv if argv is not None else sys.argv)
        app_name = raw_args[0] if raw_args else APP_NAME
        _build_parser().parse_known_args(raw_args[1:])

    with timer.stage("qt_application"):
        qt_app = QApplication.instance() or QApplication([app_name])
        qt_app.setApplicationName(APP_NAME)
        qt_app.setApplicationVersion(APP_VERSION)

    with timer.stage("configuration_load"):
        loader = EnvironmentLoader()
        config = loader.load()
        source_config = loader.load_source_config()

    with timer.stage("dependency_composition"):
        bootstrap = DemoBootstrap(config, source_config=source_config)
        factory, _startup_steps = bootstrap.bootstrap(correlation_id="corr-startup")

    with timer.stage("application_wrapper"):
        application = AIPApplication(
            raw_args,
            application_factory=factory,
        )

    with timer.stage("window_create"):
        window = application.create_window()

    snapshot = timer.snapshot()
    metrics_store = getattr(window, "_diagnostic_metrics", None)
    if isinstance(metrics_store, DiagnosticMetricsStore):
        metrics_store.record_startup_metrics(snapshot.as_dict())

    if timer.profile_enabled():
        print(StartupTimer.format_snapshot(snapshot), flush=True)

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
