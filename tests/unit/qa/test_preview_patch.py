"""Preview patches are verified and cannot touch confidential runtime state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.qa.apply_preview_patch import UpdateRejected, install, verify_payload
from scripts.qa.build_preview_patch import allowed


def _package(tmp_path: Path, source: bytes = b"NEW") -> tuple[Path, Path]:
    package = tmp_path / "package"
    file = package / "payload" / "src" / "aip" / "example.py"
    file.parent.mkdir(parents=True)
    file.write_bytes(source)
    (package / "manifest.json").write_text(
        json.dumps({
            "format": "aip-v451-preview-patch-v1",
            "repository": "vernan2020/AIP-Enterprise",
            "source_sha": "a" * 40,
            "target_name": "AIP-V451-PREVIEW",
            "files": [{"path": "src/aip/example.py",
                       "sha256": hashlib.sha256(source).hexdigest(), "size": len(source)}],
        }),
        encoding="utf-8",
    )
    target = tmp_path / "AIP-V451-PREVIEW"
    (target / "src" / "aip").mkdir(parents=True)
    (target / "run_aip_ux_preview.cmd").write_text("ECHO LIVE", encoding="utf-8")
    return package, target


def test_preview_patch_verifies_sha_and_preserves_private_data(tmp_path: Path) -> None:
    package, target = _package(tmp_path)
    existing = target / "src" / "aip" / "example.py"
    existing.write_bytes(b"OLD")
    private = target / "database" / "aip.duckdb"
    private.parent.mkdir()
    private.write_bytes(b"ORIGINAL DATA")
    credentials = target / "config" / "runtime.local.cmd"
    credentials.parent.mkdir()
    credentials.write_bytes(b"TOKEN")
    assert install(package, target, dry_run=True)["status"] == "verified_only"
    assert existing.read_bytes() == b"OLD"
    result = install(package, target)
    assert result["status"] == "applied"
    assert existing.read_bytes() == b"NEW"
    assert (Path(result["backup"]) / "src/aip/example.py").read_bytes() == b"OLD"
    assert private.read_bytes() == b"ORIGINAL DATA"
    assert credentials.read_bytes() == b"TOKEN"


def test_corrupted_package_is_rejected_before_any_write(tmp_path: Path) -> None:
    package, target = _package(tmp_path)
    (package / "payload/src/aip/example.py").write_bytes(b"TAMPERED")
    with pytest.raises(UpdateRejected, match="SHA256"):
        install(package, target)
    assert not (target / "src/aip/example.py").exists()


def test_patch_rejects_certified_release_even_with_matching_contents(tmp_path: Path) -> None:
    package, target = _package(tmp_path)
    certified = tmp_path / "AIP-Enterprise-release-core-v1.0"
    target.rename(certified)
    with pytest.raises(UpdateRejected, match="AIP-V451-PREVIEW"):
        install(package, certified)


@pytest.mark.parametrize(
    "name",
    (
        "../database/aip.duckdb",
        "src/../../certified.py",
        "database/aip.duckdb",
        "src/aip/test.ttf",
        ".venv/Lib/site-packages/tool.py",
        "config/runtime.local.cmd",
        "src/aip/.env",
        "src/aip/a.pyc",
    ),
)
def test_forbidden_paths_are_never_packaged(name: str) -> None:
    assert not allowed(name)


def test_safe_source_is_packaged() -> None:
    assert allowed("src/aip/domain/model.py")
    assert allowed("scripts/qa/diagnose_official_feeds.py")
    assert allowed("run_aip_ux_preview.cmd")
    assert not allowed("secrets.txt")
