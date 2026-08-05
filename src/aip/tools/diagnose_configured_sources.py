from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from aip.product.configured.adapters.configured_portfolio_provider import ConfiguredPortfolioProvider
from aip.product.configured.configuration.configured_source_config import (
    BCCRSourceConfig,
    ConfiguredSourceConfig,
    CurvesSourceConfig,
    FolderWatchSourceConfig,
    SQLServerSourceConfig,
    VectorSourceConfig,
)
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


class DiagnosticCommandError(RuntimeError):
    pass


def _safe_reference(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    return Path(text).name or text


def _build_config() -> tuple[DemoConfig, ConfiguredSourceConfig]:
    loader = EnvironmentLoader()
    config = loader.load()
    source_config_payload = config.source_config or {}
    source_config = ConfiguredSourceConfig(
        sql_server=SQLServerSourceConfig(
            enabled=bool(source_config_payload.get("sql_server", {}).get("enabled", False)),
            server=source_config_payload.get("sql_server", {}).get("server"),
            database=source_config_payload.get("sql_server", {}).get("database"),
            authentication_mode=source_config_payload.get("sql_server", {}).get("authentication_mode", "windows"),
            view=source_config_payload.get("sql_server", {}).get("view", "VISTA_1514_1515_1516"),
            scenario_filters=tuple(source_config_payload.get("sql_server", {}).get("scenario_filters", ())),
        ),
        folder_watch=FolderWatchSourceConfig(
            enabled=bool(source_config_payload.get("folder_watch", {}).get("enabled", False)),
            portfolio_root=source_config_payload.get("folder_watch", {}).get("portfolio_root"),
            icl_root=source_config_payload.get("folder_watch", {}).get("icl_root"),
            curves_path=source_config_payload.get("folder_watch", {}).get("curves_path"),
            vector_path=source_config_payload.get("folder_watch", {}).get("vector_path"),
            portfolio_master_pattern=source_config_payload.get("folder_watch", {}).get("portfolio_master_pattern", r"Inversiones\{year}\maestro\{month}\*.xls*"),
            icl_file_pattern=source_config_payload.get("folder_watch", {}).get("icl_file_pattern", r"ICL\Reportes ICL\*"),
        ),
        curves=CurvesSourceConfig(
            enabled=bool(source_config_payload.get("curves", {}).get("enabled", False)),
            workbook=source_config_payload.get("curves", {}).get("workbook"),
            sheet_mapping=tuple(source_config_payload.get("curves", {}).get("sheet_mapping", ())),
        ),
        vector=VectorSourceConfig(
            enabled=bool(source_config_payload.get("vector", {}).get("enabled", False)),
            path=source_config_payload.get("vector", {}).get("path"),
            root=source_config_payload.get("vector", {}).get("root"),
            directory_aliases=tuple(source_config_payload.get("vector", {}).get("directory_aliases", ())),
            file_pattern=source_config_payload.get("vector", {}).get("file_pattern"),
            supported_extensions=tuple(source_config_payload.get("vector", {}).get("supported_extensions", ())),
        ),
        bccr=BCCRSourceConfig(
            enabled=bool(source_config_payload.get("bccr", {}).get("enabled", False)),
            base_url=source_config_payload.get("bccr", {}).get("base_url"),
            timeout_seconds=float(source_config_payload.get("bccr", {}).get("timeout_seconds", 30.0)),
            retries=int(source_config_payload.get("bccr", {}).get("retries", 3)),
            cache_enabled=bool(source_config_payload.get("bccr", {}).get("cache_enabled", True)),
        ),
        diagnostic_mode=bool(source_config_payload.get("diagnostic_mode", False)),
        metadata={
            "allow_prior_source_date": bool(source_config_payload.get("allow_prior_source_date", False)),
            "data_cutoff_date": source_config_payload.get("data_cutoff_date"),
        },
    )
    return config, source_config


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        config, source_config = _build_config()
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"CONFIGURED SOURCE DIAGNOSTIC\nERROR: {exc}")
        return 2

    if config.execution_mode != "CONFIGURED":
        print("CONFIGURED SOURCE DIAGNOSTIC\nERROR: execution mode must be CONFIGURED")
        return 2

    provider = ConfiguredPortfolioProvider(config, source_config)
    payload = provider.get_portfolio()
    status = payload.get("data_quality_status", "DEGRADED")
    cutoff_date = config.data_cutoff_date

    print("CONFIGURED SOURCE DIAGNOSTIC")
    print(f"Execution mode: {config.execution_mode}")
    print(f"Cutoff: {cutoff_date.isoformat()}")
    print()
    print("MASTER")
    print(f"Status: {payload['portfolio_master'].get('status', 'UNKNOWN')}")
    print(f"File: {_safe_reference(payload['portfolio_master'].get('file_name'))}")
    print(f"Sheet: {_safe_reference(payload['portfolio_master'].get('sheet_selected'))}")
    row_count = payload['portfolio_master'].get('rejected_row_count')
    print(f"Header row: {payload['portfolio_master'].get('diagnostics', {}).get('header_row', 'N/A')}")
    print(f"Rows read: {payload['portfolio_master'].get('diagnostics', {}).get('rows_read', 'N/A')}")
    print(f"Rows accepted: {payload['portfolio_master'].get('diagnostics', {}).get('rows_accepted', 'N/A')}")
    print(f"Rows rejected: {row_count}")
    print(f"Mapped columns: {len(payload['portfolio_master'].get('detected_column_mapping', {}))}")
    print(f"ISIN count: {sum(1 for position in payload.get('positions', []) if position.get('isin'))}")
    warnings = payload['portfolio_master'].get('warnings', ())
    print(f"Warnings: {', '.join(warnings[:3]) if warnings else 'None'}")
    print()
    print("VECTOR")
    print(f"Status: {payload['price_vector'].get('status', 'UNKNOWN')}")
    print(f"File: {_safe_reference(payload['price_vector'].get('file_name'))}")
    print(f"Encoding: {payload['price_vector'].get('encoding', 'unknown')}")
    print(f"Layout: {payload['price_vector'].get('diagnostics', {}).get('layout', 'unknown')}")
    print(f"Lines read: {payload['price_vector'].get('diagnostics', {}).get('line_count', 'N/A')}")
    print(f"Records accepted: {payload['price_vector'].get('accepted_count', 'N/A')}")
    print(f"Records rejected: {payload['price_vector'].get('rejected_count', 'N/A')}")
    print(f"ISIN count: {len(payload['price_vector'].get('diagnostics', {}).get('trace', {}).get('isin_found', []))}")
    rejected_reason_counts = payload['price_vector'].get('diagnostics', {}).get('trace', {}).get('rejected_reason_counts', {})
    if rejected_reason_counts:
        print("Rejected reasons:")
        for reason, count in sorted(rejected_reason_counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"  - {reason}: {count}")
    else:
        print("Rejected reasons: None")
    accepted_records = payload['price_vector'].get('diagnostics', {}).get('trace', {}).get('accepted_records', [])
    if accepted_records:
        print("Accepted vector diagnostics:")
        for entry in accepted_records[:3]:
            print(
                "  - line {line}: issuer={issuer} mnemonic={mnemonic} series={series} maturity={maturity} normalized_series={nseries} normalized_issuer={nissuer}".format(
                    line=entry.get('line', 'N/A'),
                    issuer=entry.get('issuer', ''),
                    mnemonic=entry.get('mnemonic', ''),
                    series=entry.get('series_or_security_code', ''),
                    maturity=entry.get('maturity_date', ''),
                    nseries=entry.get('normalized_series_key', ''),
                    nissuer=entry.get('normalized_issuer_key', ''),
                )
            )
    print("Warnings: None")
    print()
    print("MATCHING")
    match_summary = payload.get('portfolio_master', {}).get('diagnostics', {}).get('matching', {})
    if not match_summary:
        match_summary = payload.get('diagnostics', {}).get('portfolio_master', {}).get('matching', {})
    print(f"Positions: {len(payload.get('positions', []))}")
    print(f"Matched by ISIN: {match_summary.get('exact_isin_matches', 0)}")
    print(f"Matched by series/maturity: {match_summary.get('series_maturity_matches', 0)}")
    print(f"Matched by issuer/product/maturity: {match_summary.get('issuer_product_maturity_matches', 0)}")
    print(f"Ambiguous: {match_summary.get('ambiguous_matches', 0)}")
    print(f"Unmatched: {match_summary.get('unmatched_positions', 0)}")
    print(f"Match percentage: {match_summary.get('match_percentage', 0.0)}")
    if payload.get('positions'):
        print("Position diagnostics:")
        for position in payload['positions'][:3]:
            diagnostics = position.get('matching_diagnostics', {})
            print(
                "  - line {line}: isin={isin} series={series} maturity={maturity} issuer={issuer} product={product} keys={keys}".format(
                    line=position.get('source_row', 'N/A'),
                    isin=diagnostics.get('normalized_isin', ''),
                    series=diagnostics.get('normalized_series', ''),
                    maturity=diagnostics.get('maturity_date', ''),
                    issuer=diagnostics.get('normalized_issuer', ''),
                    product=diagnostics.get('normalized_product_code', ''),
                    keys=diagnostics.get('matching_keys', {}),
                )
            )
    print()
    print("ALIGNMENT")
    print(f"Master cutoff: {payload['portfolio_master'].get('valuation_date', 'N/A')}")
    print(f"Vector cutoff: {payload['price_vector'].get('valuation_date', 'N/A')}")
    print(f"Status: {status}")

    if status in {"HEALTHY", "DEGRADED"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
