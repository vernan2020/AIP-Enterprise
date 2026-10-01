from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

PACKAGE_ROOT = PurePosixPath("AIP_RC1_CERTIFIED")
REQUIRED_TOP_LEVEL = {
    (PACKAGE_ROOT / "manifest.json").as_posix(),
    (PACKAGE_ROOT / "apply_windows_recovery.py").as_posix(),
    (PACKAGE_ROOT / "APPLY_TO_PROJECT.cmd").as_posix(),
}

REQUIRED_SOURCE_CONTRACTS: dict[str, tuple[str, ...]] = {
    "src/aip/integration/bccr/connector/cache.py": (
        "def set(self, key: str, value: Any, *, ttl_seconds: int | None = None)",
        "def size(self) -> int:",
    ),
    "src/aip/ui/modules/portfolio/views/portfolio_view.py": (
        'self._tabs.addTab(self._valuation_comparison, "Ganancia / pérdida")',
    ),
    "src/aip/ui/modules/portfolio/widgets/portfolio_history_line_chart.py": (
        "def _draw_hover_card(",
        "def _draw_latest_value_pill(",
        "def _draw_time_axis(",
    ),
    "scripts/recovery/verify_release_ui_contract.py": (
        "AIP RELEASE UI CONTRACT: CURRENT",
    ),
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_zip_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe ZIP member: {name}")
    if not path.parts or path.parts[0] != PACKAGE_ROOT.name:
        raise RuntimeError(f"ZIP member is outside package root: {name}")


def verify_package(path: Path) -> tuple[int, str]:
    if not path.is_file():
        raise RuntimeError(f"Recovery package not found: {path}")

    package_digest = hashlib.sha256(path.read_bytes()).hexdigest()

    with zipfile.ZipFile(path, "r") as archive:
        names = {info.filename for info in archive.infolist() if not info.is_dir()}
        for name in names:
            _validate_zip_member(name)

        missing_top = sorted(REQUIRED_TOP_LEVEL - names)
        if missing_top:
            raise RuntimeError(
                "Recovery package is structurally incomplete: " + ", ".join(missing_top)
            )

        manifest_name = (PACKAGE_ROOT / "manifest.json").as_posix()
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise RuntimeError("Recovery package manifest must be a JSON object")

        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise RuntimeError("Recovery package manifest does not declare payload files")

        declared: set[str] = set()
        for entry in files:
            if not isinstance(entry, dict):
                raise RuntimeError("Invalid recovery package manifest entry")
            relative = entry.get("path")
            expected_hash = entry.get("sha256")
            expected_size = entry.get("size")
            if not isinstance(relative, str) or not relative:
                raise RuntimeError("Invalid payload path in recovery manifest")
            relative_path = PurePosixPath(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise RuntimeError(f"Unsafe payload path in manifest: {relative}")
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                raise RuntimeError(f"Invalid SHA-256 in manifest for {relative}")
            if not isinstance(expected_size, int) or expected_size < 0:
                raise RuntimeError(f"Invalid size in manifest for {relative}")

            member_name = (PACKAGE_ROOT / "payload" / relative_path).as_posix()
            if member_name not in names:
                raise RuntimeError(f"Declared payload file missing from ZIP: {relative}")
            data = archive.read(member_name)
            if len(data) != expected_size:
                raise RuntimeError(
                    f"Payload size mismatch for {relative}: expected {expected_size}, got {len(data)}"
                )
            actual_hash = _sha256_bytes(data)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Payload checksum mismatch for {relative}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            declared.add(member_name)

        actual_payload = {
            name for name in names if name.startswith((PACKAGE_ROOT / "payload").as_posix() + "/")
        }
        missing = sorted(declared - actual_payload)
        extra = sorted(actual_payload - declared)
        if missing or extra:
            raise RuntimeError(
                "Recovery payload set mismatch: "
                f"missing={missing or 'none'}, extra={extra or 'none'}"
            )

        if manifest.get("file_count") != len(files):
            raise RuntimeError(
                "Recovery manifest file_count mismatch: "
                f"declared {manifest.get('file_count')}, listed {len(files)}"
            )

        for relative, markers in REQUIRED_SOURCE_CONTRACTS.items():
            member_name = (PACKAGE_ROOT / "payload" / PurePosixPath(relative)).as_posix()
            if member_name not in names:
                raise RuntimeError(f"Recovery package missing required contract file: {relative}")
            content = archive.read(member_name).decode("utf-8", errors="replace")
            missing_markers = [marker for marker in markers if marker not in content]
            if missing_markers:
                raise RuntimeError(
                    f"Recovery package has stale contract file {relative}: "
                    + ", ".join(missing_markers)
                )

    return len(files), package_digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify AIP certified Windows recovery ZIP")
    parser.add_argument(
        "package",
        nargs="?",
        default="dist/AIP-Enterprise-RC1-Certified-Windows.zip",
    )
    args = parser.parse_args(argv)

    package = Path(args.package)
    count, digest = verify_package(package)
    print(f"Recovery ZIP integrity: PASS ({count} payload files)")
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
