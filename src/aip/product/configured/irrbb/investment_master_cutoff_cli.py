"""Read-only investment-master cutoff evidence for AIP configured RTILB."""

from __future__ import annotations

import argparse
import json
from datetime import date

from aip.product.configured.irrbb.investment_master_cutoff_audit import (
    inspect_investment_master_cutoff,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIP RTILB: Maestro institucional del corte")
    parser.add_argument("--cutoff", default="2026-09-30")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("--cutoff requires YYYY-MM-DD")
    try:
        folder = EnvironmentLoader().load_source_config().folder_watch
        result = inspect_investment_master_cutoff(cutoff=cutoff, folder=folder)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
