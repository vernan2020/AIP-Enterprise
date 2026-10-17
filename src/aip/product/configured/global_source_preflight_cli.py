"""Read-only local source preflight for the real AIP configured runtime.

Do not claim API, SQL or financial module availability from configuration alone.
Never serialize paths, credentials, identifiers or private data.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.configuration.institutional_paths import (
    expand_environment_path,
)
from aip.product.configured.irrbb.investment_master_discovery import (
    find_exact_cutoff_master,
)
from aip.product.configured.irrbb.xml_confia_source import (
    XML_CONFIA_SOURCE_STEMS,
    XMLConfiaMonthlySourceReader,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def _path_status(value: str | None, *, file_only: bool = False) -> str:
    if not value:
        return "UNCONFIGURED"
    try:
        path = Path(expand_environment_path(value) or "")
        exists = path.is_file() if file_only else path.is_dir()
    except (OSError, ValueError):
        return "INACCESSIBLE"
    return "PRESENT" if exists else "NOT_FOUND"


def preflight(
    cutoff: date, config: ConfiguredSourceConfig, *, environment: dict[str, str]
) -> dict[str, object]:
    """Inspect local source presence; never test remote connectivity implicitly."""
    sources: dict[str, dict[str, object]] = {}
    folder = config.folder_watch
    sources["investment_master_root"] = {
        "status": (_path_status(folder.portfolio_root) if folder.enabled else "DISABLED"),
        "scope": "Directory only; latest master and certification not assessed",
    }
    investment_status, match_count = find_exact_cutoff_master(
        folder.portfolio_root if folder.enabled else None,
        folder.portfolio_master_pattern,
        cutoff,
    )
    sources["investment_master_cutoff"] = {
        "status": investment_status,
        "matching_file_count": match_count,
        "scope": (
            "Exact-cutoff master candidate only; contents, position mapping, "
            "source certification and cash flows not verified. XML investment "
            "source is reconciliation only."
        ),
    }
    sources["icl_root"] = {
        "status": _path_status(folder.icl_root) if folder.enabled else "DISABLED",
        "scope": "Directory only; ICL data and ratios not validated",
    }
    sources["market_vector"] = {
        "status": (
            _path_status(config.vector.path, file_only=True)
            if config.vector.enabled
            else "DISABLED"
        ),
        "scope": "Configured file only; price date and content not validated",
    }
    sources["yield_curves"] = {
        "status": (
            _path_status(config.curves.workbook, file_only=True)
            if config.curves.enabled
            else "DISABLED"
        ),
        "scope": "Configured file only; curves not calibrated",
    }
    sources["sql_server_financial"] = {
        "status": (
            "CONFIGURED_NETWORK_NOT_TESTED"
            if config.sql_server.enabled and config.sql_server.server
            else ("UNCONFIGURED" if config.sql_server.enabled else "DISABLED")
        ),
        "scope": "No SQL connections, views or values were queried",
    }
    bccr = config.bccr
    sources["bccr_api"] = {
        "status": (
            "CONFIGURED_NETWORK_NOT_TESTED"
            if bccr.enabled and bccr.name and bccr.email and bccr.token
            else ("MISSING_CREDENTIAL_CONFIGURATION" if bccr.enabled else "DISABLED")
        ),
        "scope": "Credentials presence only; no SDDE request or cache freshness checked",
    }
    sugef = config.sugef_financial
    sources["sugef_financial"] = {
        "status": (
            "CONFIGURED_NETWORK_NOT_TESTED"
            if sugef.enabled and sugef.api_enabled
            else (_path_status(sugef.root) if sugef.enabled else "DISABLED")
        ),
        "scope": "No API request, historical refresh or published cutoff verified",
    }
    xml = config.xml_confia
    xml_statuses: dict[str, str] = {}
    if xml.enabled and xml.root:
        root = expand_environment_path(xml.root)
        try:
            reader = XMLConfiaMonthlySourceReader(root or "")
            for name in XML_CONFIA_SOURCE_STEMS:
                try:
                    reader.resolve_source(key=name, cutoff_date=cutoff)
                except (OSError, ValueError, KeyError):
                    xml_statuses[name] = "NOT_AVAILABLE_FOR_CUTOFF"
                else:
                    xml_statuses[name] = "HEADER_MATCHES_CUTOFF"
        except (OSError, ValueError):
            xml_statuses = {name: "SOURCE_UNAVAILABLE" for name in XML_CONFIA_SOURCE_STEMS}
    else:
        xml_statuses = {name: "UNCONFIGURED" for name in XML_CONFIA_SOURCE_STEMS}
    sources["xml_confia"] = {
        "status": "HEADERS_INSPECTED",
        "cutoff_sources": xml_statuses,
        "scope": "Month and header only; source amounts and full data not certified",
    }
    sources["runtime"] = {
        "status": (
            "CONFIGURED"
            if environment.get("AIP_EXECUTION_MODE", "").upper() == "CONFIGURED"
            and environment.get("AIP_DEMO_MODE_ENABLED", "false").lower() == "false"
            else "MODE_NOT_VERIFIED"
        ),
        "scope": "This diagnostic does not start or test every UI module",
    }
    return {
        "status": "LOCAL_SOURCE_PREFLIGHT_ONLY",
        "cutoff": cutoff.isoformat(),
        "sources": sources,
        "note": (
            "No network calls, SQL queries, source writes or financial calculations. "
            "Configuration presence is NOT evidence of application readiness."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIP configured source preflight")
    parser.add_argument("--cutoff", default="2026-09-30")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("--cutoff requires YYYY-MM-DD")
    config = EnvironmentLoader().load_source_config()
    print(
        json.dumps(
            preflight(cutoff, config, environment=dict(os.environ)),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
