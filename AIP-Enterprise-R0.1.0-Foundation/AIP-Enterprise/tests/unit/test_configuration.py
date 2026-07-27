from pathlib import Path
from aip.infrastructure.configuration.manager import ConfigurationManager


def test_load_configuration(tmp_path: Path) -> None:
    (tmp_path / "application.yaml").write_text("application:\n  name: Test AIP\n", encoding="utf-8")
    (tmp_path / "database.yaml").write_text("database:\n  path: test.duckdb\n", encoding="utf-8")
    (tmp_path / "logging.yaml").write_text("logging:\n  level: DEBUG\n", encoding="utf-8")
    settings = ConfigurationManager(tmp_path).load()
    assert settings.application.name == "Test AIP"
    assert settings.database.path == Path("test.duckdb")
    assert settings.logging.level == "DEBUG"
