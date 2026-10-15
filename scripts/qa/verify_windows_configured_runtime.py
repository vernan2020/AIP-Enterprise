"""Windows-native smoke check for the real CONFIGURED runtime resolver.

Uses temporary synthetic tokens only. Does not inspect certified installations,
connect to BCCR, or disclose private environment values.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def _run_case(
    *,
    resolver: Path,
    workdir: Path,
    expected_token: str | None,
    override: Path | None = None,
    inherited: str | None = None,
    expect_failure: bool = False,
) -> None:
    env = os.environ.copy()
    env.pop("AIP_RUNTIME_LOCAL_CMD", None)
    env.pop("AIP_BCCR_TOKEN", None)
    if override is not None:
        env["AIP_RUNTIME_LOCAL_CMD"] = str(override)
    if inherited is not None:
        env["AIP_BCCR_TOKEN"] = inherited

    assertion = (
        "exit /b 0"
        if expect_failure
        else (
            f'if not "%AIP_BCCR_TOKEN%"=="{expected_token}" exit /b 3'
            + "\nexit /b 0"
        )
    )
    # CMD expands variables independently for each line of this temporary file,
    # after the resolver's CALL has completed.
    batch = workdir / "smoke.cmd"
    batch.write_text(
        "@echo off\n"
        f'call "{resolver}" >nul\n'
        + ("if not errorlevel 1 exit /b 4\n" if expect_failure else "if errorlevel 1 exit /b 5\n")
        + assertion
        + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", str(batch)],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"CONFIGURED resolver case failed (exit={completed.returncode}); "
            "output and credentials intentionally withheld"
        )


def main() -> int:
    if os.name != "nt":
        return 0
    resolver = (
        Path(__file__).resolve().parents[1] / "launch" / "load_existing_institutional_runtime.cmd"
    )
    if not resolver.is_file():
        raise SystemExit("CONFIGURED resolver not found")

    with tempfile.TemporaryDirectory(prefix="aip-configured-qa-") as temporary:
        root = Path(temporary)
        preview = root / "config"
        preview.mkdir()
        preview_file = preview / "runtime.local.cmd"
        preview_file.write_text('@echo off\nset "AIP_BCCR_TOKEN=PREVIEW_TEST"\n', encoding="utf-8")

        override_file = root / "explicit.cmd"
        override_file.write_text('@echo off\nset "AIP_BCCR_TOKEN=EXPLICIT_TEST"\n', encoding="utf-8")
        _run_case(
            resolver=resolver,
            workdir=root,
            override=override_file,
            expected_token="EXPLICIT_TEST",
        )
        _run_case(resolver=resolver, workdir=root, expected_token="PREVIEW_TEST")

        preview_file.unlink()
        _run_case(
            resolver=resolver,
            workdir=root,
            inherited="INHERITED_TEST",
            expected_token="INHERITED_TEST",
        )
        _run_case(
            resolver=resolver,
            workdir=root,
            override=root / "missing-private.cmd",
            expected_token=None,
            expect_failure=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
