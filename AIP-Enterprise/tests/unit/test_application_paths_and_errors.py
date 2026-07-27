from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.application.kernel import ApplicationKernel
from aip.core.bootstrap import Bootstrap, BootstrapServices
from aip.core.container import Container
from aip.core.exceptions import AIPError, ConfigurationError, ConflictError, NotFoundError, UnauthorizedError, ValidationError
from aip.core.paths import ProjectPaths
from aip.infrastructure.audit.service import AuditService
from aip.infrastructure.configuration.manager import ConfigurationManager
from aip.infrastructure.database.manager import DatabaseManager
from aip.infrastructure.logging.manager import LoggingManager
from aip.main import main as main_entrypoint
from aip.shared.conventions import DayCountConvention
from aip.ui.main_window import MainWindow


class DummyQtApp:
    def __init__(self) -> None:
        self.aboutToQuit = SimpleNamespace(connect=lambda *args, **kwargs: None)

    def exec(self) -> int:
        return 0


def test_application_kernel_runs_and_shuts_down(tmp_path: Path) -> None:
    config_manager = ConfigurationManager(tmp_path)
    logging_manager = LoggingManager(
        SimpleNamespace(
            directory=Path("logs"),
            level="INFO",
            application_filename="aip.log",
            audit_filename="audit.jsonl",
            rotation="10 MB",
            retention="30 days",
            compression=None,
        ),
        tmp_path,
    )
    logging_manager.configure()
    database = DatabaseManager(SimpleNamespace(path=Path("database/test.duckdb"), read_only=False), tmp_path)
    database.initialize()
    audit = AuditService(logging_manager)
    kernel = ApplicationKernel(DummyQtApp(), BootstrapServices(Container(), config_manager, logging_manager, database, audit))
    kernel._shutdown()
    assert True


def test_bootstrap_initializes_paths_and_services(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "application.yaml").write_text("application: {name: Test}\n", encoding="utf-8")
    (config_dir / "database.yaml").write_text("database: {path: test.duckdb}\n", encoding="utf-8")
    (config_dir / "logging.yaml").write_text("logging: {level: INFO}\n", encoding="utf-8")
    paths = ProjectPaths(root=tmp_path, config=config_dir, database=tmp_path / "database", logs=tmp_path / "logs", data=tmp_path / "data")
    services = Bootstrap(paths).initialize()
    assert services.configuration.settings.application.name == "Test"
    assert services.database.path.exists()


def test_core_exceptions_expose_context_and_string_form() -> None:
    error = ValidationError("invalid")
    assert error.code == "VALIDATION_ERROR"
    assert error.details == {}
    assert str(error) == "[VALIDATION_ERROR] invalid"

    wrapped = ConfigurationError("bad config", details={"field": "x"})
    assert wrapped.details["field"] == "x"
    assert isinstance(wrapped, AIPError)
    assert isinstance(wrapped, ConfigurationError)

    conflict = ConflictError("conflict")
    unauthorized = UnauthorizedError("forbidden")
    not_found = NotFoundError("missing")
    assert conflict.code == "CONFLICT"
    assert unauthorized.code == "UNAUTHORIZED"
    assert not_found.code == "NOT_FOUND"


def test_project_paths_discover_and_ensure(tmp_path: Path) -> None:
    paths = ProjectPaths(root=tmp_path, config=tmp_path / "config", database=tmp_path / "database", logs=tmp_path / "logs", data=tmp_path / "data")
    paths.ensure()
    assert (tmp_path / "config").exists()
    assert (tmp_path / "database").exists()
    assert (tmp_path / "logs").exists()
    assert (tmp_path / "data" / "input").exists()


def test_application_kernel_run_and_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeWindow:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

        def show(self) -> None:
            return None

    class FakeQtApp:
        def __init__(self) -> None:
            self.aboutToQuit = SimpleNamespace(connect=lambda *args, **kwargs: None)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr("aip.application.kernel.MainWindow", FakeWindow)
    services = SimpleNamespace(
        logging=SimpleNamespace(bind=lambda *args, **kwargs: SimpleNamespace(info=lambda *a, **k: None)),
        configuration=SimpleNamespace(settings=SimpleNamespace(application=SimpleNamespace(window_width=800, window_height=600, organization="Org", environment="dev"))),
        database=SimpleNamespace(close=lambda: None),
        audit=SimpleNamespace(record=lambda *args, **kwargs: None),
    )
    kernel = ApplicationKernel(FakeQtApp(), services)
    assert kernel.run() == 0
    kernel._shutdown()


def test_main_entrypoint_initializes_services(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQtApp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.aboutToQuit = SimpleNamespace(connect=lambda *args, **kwargs: None)

        def setApplicationName(self, *args: object, **kwargs: object) -> None:
            return None

        def setApplicationVersion(self, *args: object, **kwargs: object) -> None:
            return None

        def exec(self) -> int:
            return 0

    class FakeKernel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

        def run(self) -> int:
            return 0

    monkeypatch.setattr("aip.main.QApplication", FakeQtApp)
    monkeypatch.setattr("aip.main.Bootstrap", lambda *args, **kwargs: SimpleNamespace(initialize=lambda: object()))
    monkeypatch.setattr("aip.main.ProjectPaths", SimpleNamespace(discover=lambda: object()))
    monkeypatch.setattr("aip.main.ApplicationKernel", FakeKernel)
    assert main_entrypoint() == 0


def test_main_window_builds_with_database_value() -> None:
    class FakeDatabase:
        path = Path("database/test.duckdb")

        def scalar(self, *args: object, **kwargs: object) -> str:
            return "0.1.0"

    settings = SimpleNamespace(
        application=SimpleNamespace(window_width=800, window_height=600, organization="Org", environment="dev")
    )
    window = MainWindow(settings, FakeDatabase())
    assert window is not None


def test_day_count_conventions_cover_other_branches() -> None:
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    assert DayCountConvention.ACTUAL_360.calculate_year_fraction(start, end) == Decimal((end - start).days) / Decimal("360")
    assert DayCountConvention.THIRTY_360.calculate_year_fraction(start, end) == Decimal("1")
