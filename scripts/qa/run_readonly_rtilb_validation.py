"""Read-only institutional RTILB diagnosis orchestration for Windows PREVIEW.

Runs existing, already-governed CMD diagnostics with one exact cutoff. Captures
results in memory; only safe status metadata is printed or written to disk.
Raw sensitive XML summaries, amounts, source paths and tokens are never persisted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import date
from pathlib import Path

CHECKS = (
    ("GLOBAL_SOURCES", "DIAGNOSTICAR_AIP_GLOBAL.cmd"),
    ("SIX_BAND_XML", "DIAGNOSTICAR_RTILB_XML.cmd"),
    ("CONTRACTUAL_COVERAGE", "DIAGNOSTICAR_RTILB_COBERTURA_XML.cmd"),
    ("CONTRACTUAL_PRODUCTS", "DIAGNOSTICAR_RTILB_PRODUCTOS_XML.cmd"),
    ("CONTRACTUAL_EXPOSURE", "DIAGNOSTICAR_RTILB_EXPOSICION_XML.cmd"),
    ("TERM_MATURITY_19", "DIAGNOSTICAR_RTILB_BANDEO_19_EVIDENCIA.cmd"),
)

EXPECTED_STATUS = {
    "GLOBAL_SOURCES": "LOCAL_SOURCE_PREFLIGHT_ONLY",
    "SIX_BAND_XML": "VALIDATED",
    "CONTRACTUAL_COVERAGE": "COVERAGE_INSPECTED",
    "CONTRACTUAL_PRODUCTS": "AGGREGATE_GAPS_INSPECTED",
    "CONTRACTUAL_EXPOSURE": "AGGREGATE_EXPOSURE_AUDITED",
    "TERM_MATURITY_19": "MATURITY_EVIDENCE_ONLY_NOT_IRRBB_GAP",
}
SUCCESS_STATUSES = frozenset(EXPECTED_STATUS.values())


def _safe_status(stdout: str) -> str:
    """Never expose arbitrary child output, errors or source data."""
    for line in stdout.splitlines():
        if line.lstrip().startswith("{"):
            try:
                body = json.loads("\n".join(stdout.splitlines()[stdout.splitlines().index(line):]))
            except (json.JSONDecodeError, ValueError):
                break
            if isinstance(body, dict):
                status = body.get("status")
                if isinstance(status, str) and status in SUCCESS_STATUSES:
                    return status
            break
    return "NOT_CONFIRMED"


def execute_suite(root: Path, cutoff: date, *, timeout_seconds: int = 600) -> dict:
    results: list[dict[str, object]] = []
    for name, filename in CHECKS:
        path = root / filename
        if not path.is_file():
            results.append({"check": name, "result": "MISSING_DIAGNOSTIC", "seconds": 0})
            continue
        started = time.monotonic()
        try:
            child = subprocess.run(
                ["cmd.exe", "/d", "/c", "call", filename, "--cutoff", cutoff.isoformat()],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            results.append(
                {"check": name, "result": "TIMEOUT", "seconds": round(time.monotonic() - started, 1)}
            )
            continue
        except OSError:
            results.append(
                {"check": name, "result": "EXECUTION_ERROR", "seconds": round(time.monotonic() - started, 1)}
            )
            continue
        status = _safe_status(child.stdout)
        results.append(
            {
                "check": name,
                "result": (
                    "PASSED_EVIDENCE_ONLY"
                    if child.returncode == 0 and status == EXPECTED_STATUS[name]
                    else "BLOCKED"
                ),
                "status": status,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
    return {
        "status": "READ_ONLY_VALIDATION_REPORT",
        "cutoff": cutoff.isoformat(),
        "checks": results,
        "all_diagnostics_passed": all(
            x["result"] == "PASSED_EVIDENCE_ONLY" for x in results
        ),
        "certified_gap_19": False,
        "financial_modules_certified": False,
        "note": "Diagnostics and source evidence only; no live GUI KPI or ΔEVE/ΔNII certification.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run institutional RTILB preflight without writes to sources")
    parser.add_argument("--cutoff", default="2026-09-30")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("Expected YYYY-MM-DD cutoff")
    root = Path(__file__).resolve().parents[2]
    report = execute_suite(root, cutoff)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_diagnostics_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
