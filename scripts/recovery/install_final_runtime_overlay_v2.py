from __future__ import annotations

import hashlib
from pathlib import Path
import runpy
import sys
import tempfile
from urllib.request import Request, urlopen


REPOSITORY = "vernan2020/AIP-Enterprise"
BASE_INSTALLER_COMMIT = "52e9228b652f2c2a2a668e5dff783c81169db3e5"
BASE_INSTALLER_PATH = "scripts/recovery/install_final_runtime_overlay.py"
BASE_INSTALLER_BLOB_SHA = "e9a670ecffa88c6bcaa1348576cd647ec469cc67"
TARGET_SHA = "d6cb596467bbabeec557fbee735f25d57b5786c6"
USER_AGENT = "AIP-Enterprise-RC1-Final-Overlay/1.1"


def _git_blob_sha(data: bytes) -> str:
    prefix = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(prefix + data).hexdigest()


def _download_base_installer() -> bytes:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/"
        f"{BASE_INSTALLER_COMMIT}/{BASE_INSTALLER_PATH}"
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        data = response.read()
    if not data:
        raise RuntimeError("GitHub returned an empty final overlay installer")
    actual = _git_blob_sha(data)
    if actual != BASE_INSTALLER_BLOB_SHA:
        raise RuntimeError(
            "Final overlay installer integrity failure: "
            f"expected {BASE_INSTALLER_BLOB_SHA}, got {actual}"
        )
    return data


def main() -> int:
    print("=== AIP ENTERPRISE RC1 - FINAL UI/RUNTIME INSTALLER V2 ===")
    print(f"Immutable runtime/UI target: {TARGET_SHA}")
    data = _download_base_installer()
    with tempfile.TemporaryDirectory(prefix="aip-final-overlay-v2-") as directory:
        installer = Path(directory) / "install_final_runtime_overlay.py"
        installer.write_bytes(data)
        namespace = runpy.run_path(str(installer), run_name="aip_final_overlay_base")
        namespace["TARGET_SHA"] = TARGET_SHA
        namespace["USER_AGENT"] = USER_AGENT
        original_argv = list(sys.argv)
        try:
            sys.argv = [str(installer), "--project-root", str(Path.cwd())]
            result = namespace["main"]()
        finally:
            sys.argv = original_argv
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
