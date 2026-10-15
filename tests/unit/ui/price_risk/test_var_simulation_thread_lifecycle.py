"""Guard startup against premature portfolio VaR QThread creation.

The configured institutional application opens Risk of Price before the user asks
for a simulation. Its 500-scenario calculation must never start at startup.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from aip.ui.modules.price_risk.views.portfolio_var_simulator_view import (
    PortfolioVaRSimulatorView,
)


class _Presenter:
    pass


def test_var_simulator_does_not_spawn_thread_on_startup(qt_app) -> None:
    view = PortfolioVaRSimulatorView(_Presenter())  # type: ignore[arg-type]
    try:
        assert view._thread is None
        assert view._worker is None
        assert not view._busy
        view.shutdown()
        assert view._thread is None
        assert view._closing
    finally:
        view.close()


def test_var_simulator_worker_joins_when_its_page_closes(qt_app) -> None:
    view = PortfolioVaRSimulatorView(_Presenter())  # type: ignore[arg-type]
    try:
        view._setup_worker()
        assert view._thread is not None
        thread = view._thread
        view.shutdown()
        assert not thread.isRunning()
        view.shutdown()  # Idempotent across closeEvent and application shutdown.
    finally:
        view.close()
        qt_app.processEvents()


def test_var_simulator_closed_view_cannot_restart_worker(qt_app) -> None:
    view = PortfolioVaRSimulatorView(_Presenter())  # type: ignore[arg-type]
    try:
        view.shutdown()
        view._setup_worker()
        assert view._thread is None
        assert QApplication.instance() is not None
    finally:
        view.close()
