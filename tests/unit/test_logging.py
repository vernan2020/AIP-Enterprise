from pathlib import Path

from aip.infrastructure.configuration.models import LoggingSettings
from aip.infrastructure.logging.manager import LoggingManager


def test_logging_creates_directory(tmp_path: Path) -> None:
    manager = LoggingManager(LoggingSettings(directory=Path("logs")), tmp_path)
    manager.configure()
    manager.bind(component="TEST").info("mensaje de prueba")
    assert (tmp_path / "logs").exists()
