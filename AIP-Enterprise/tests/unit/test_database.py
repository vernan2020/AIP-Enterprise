from pathlib import Path
from aip.infrastructure.configuration.models import DatabaseSettings
from aip.infrastructure.database.manager import DatabaseManager


def test_database_initialization(tmp_path: Path) -> None:
    manager = DatabaseManager(DatabaseSettings(path=Path("database/test.duckdb")), tmp_path)
    manager.initialize()
    try:
        assert manager.path.exists()
        assert manager.scalar("SELECT value FROM system_metadata WHERE key = 'schema_version'") == "0.1.0"
    finally:
        manager.close()
