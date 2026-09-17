from pathlib import Path

from aip.infrastructure.configuration.manager import ConfigurationManager


def test_load_configuration(tmp_path: Path) -> None:
    (tmp_path / "application.yaml").write_text(
        "application:\n"
        "  name: Test AIP\n"
        "irrbb:\n"
        "  power_bi_semantic_routes:\n"
        "    irrbb.sources.credit.power_bi:\n"
        "      dataset_id: 22345678-1234-4234-8234-1234567890ab\n"
        "      workspace_id: null\n"
        "      authentication_profile_key: security.auth.power_bi.readonly\n",
        encoding="utf-8",
    )
    (tmp_path / "database.yaml").write_text("database:\n  path: test.duckdb\n", encoding="utf-8")
    (tmp_path / "logging.yaml").write_text("logging:\n  level: DEBUG\n", encoding="utf-8")
    settings = ConfigurationManager(tmp_path).load()
    assert settings.application.name == "Test AIP"
    assert settings.database.path == Path("test.duckdb")
    assert settings.logging.level == "DEBUG"

    route = settings.irrbb.power_bi_semantic_routes["irrbb.sources.credit.power_bi"]
    assert route.dataset_id == "22345678-1234-4234-8234-1234567890ab"
    assert route.workspace_id is None
    assert route.authentication_profile_key == "security.auth.power_bi.readonly"
