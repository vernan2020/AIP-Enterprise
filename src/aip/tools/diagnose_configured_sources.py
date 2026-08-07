from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from aip.product.configured.services.institutional_matching_service import InstitutionalPortfolioMatchingService

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


def _redact_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value)
    if not text:
        return ""
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


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


def _trace_security(payload: dict[str, Any], *, trace_security: str | None) -> None:
    if not trace_security:
        return
    print()
    print(f"TRACE {trace_security}")
    vector_records = payload.get('price_vector', {}).get('records', [])
    vector_matches = [record for record in vector_records if str(record.get('series_or_security_code', '')).upper() == trace_security.upper()]
    print("STEP 1")
    print(f"accepted_records_count: {payload['price_vector'].get('accepted_count', 0)}")
    if vector_matches:
        record = vector_matches[0]
        print(f"issuer: {record.get('issuer', '')}")
        print(f"product_code: {record.get('instrument_type_or_mnemonic', '')}")
        print(f"series: {record.get('series_or_security_code', '')}")
        print(f"maturity_date: {record.get('maturity_date_if_present')}")
    print("STEP 2")
    print(f"len(price_vector.positions): {len(payload.get('positions', []))}")
    for position in payload.get('positions', []):
        if str(position.get('series', '')).upper() == trace_security.upper():
            print(f"issuer: {position.get('issuer', '')}")
            print(f"product_code: {position.get('product_code', '')}")
            print(f"series: {position.get('series', '')}")
            print(f"maturity_date: {position.get('maturity_date')}")
            break
    print("STEP 3")
    matching = payload.get('portfolio_master', {}).get('diagnostics', {}).get('matching', {})
    if not matching:
        matching = payload.get('diagnostics', {}).get('portfolio_master', {}).get('matching', {})
    if matching:
        trace = matching.get('trace', [])
        if trace:
            print(f"len(vector_positions): {len(trace)}")
            for item in trace:
                if str(item.get('normalized_series', '')).upper() == trace_security.upper():
                    print(item)
                    break
    print("STEP 4")
    print(f"series_maturity: {matching.get('master_key_sample', {}).get('series_maturity') if isinstance(matching.get('master_key_sample'), dict) else None}")
    print(f"issuer_product_maturity: {matching.get('master_key_sample', {}).get('issuer_product_maturity') if isinstance(matching.get('master_key_sample'), dict) else None}")
    print("STEP 5")
    print(f"master_keys: {matching.get('master_key_sample')}")
    print("STEP 6")
    lookup_result = matching.get('lookup_result') or {}
    if isinstance(lookup_result, dict):
        print(f"lookup(series_maturity): {lookup_result.get('series_maturity')}")
        print(f"lookup(issuer_product_maturity): {lookup_result.get('issuer_product_maturity')}")
    else:
        print("lookup(series_maturity): None")
        print("lookup(issuer_product_maturity): None")
    print("STEP 7")
    print(f"matched_by_series_maturity: {matching.get('series_maturity_matches', 0)}")
    print("STEP 8")
    print("trace_complete: true")


def _extract_match_summary(payload: dict[str, Any]) -> dict[str, Any]:
    match_summary = payload.get("portfolio_master", {}).get("diagnostics", {}).get("matching", {})
    if not match_summary:
        match_summary = payload.get("diagnostics", {}).get("portfolio_master", {}).get("matching", {})
    return match_summary if isinstance(match_summary, dict) else {}


def _normalize_report_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", "", text).casefold()


def _compose_report_key(series: Any, maturity_date: Any) -> str:
    values: list[str] = []
    series_text = _normalize_report_text(series)
    if series_text:
        values.append(series_text)
    if isinstance(maturity_date, date):
        values.append(maturity_date.isoformat())
    elif maturity_date is not None and str(maturity_date).strip():
        values.append(str(maturity_date).strip())
    return "|".join(values)


def _print_reconciliation_sections(payload: dict[str, Any], match_summary: dict[str, Any], *, diagnostic_mode: bool) -> None:
    reconciliation = match_summary.get("reconciliation", {}) if isinstance(match_summary.get("reconciliation", {}), dict) else {}
    print()
    print("RECONCILIATION")
    for field_name in (
        "total_master_positions",
        "eligible_fixed_income_positions",
        "matched_positions",
        "expected_unmatched_positions",
        "review_required_positions",
        "raw_match_percentage",
        "eligible_match_percentage",
        "vector_key_collisions",
        "collisions_affecting_portfolio",
    ):
        print(f"{field_name}: {reconciliation.get(field_name, 0)}")

    print()
    print("UNMATCHED REASON SUMMARY")
    unmatched_reason_groups = reconciliation.get("unmatched_reason_groups", {}) or {}
    rendered_reasons = [
        f"{reason} -> {count}"
        for reason, count in sorted(unmatched_reason_groups.items(), key=lambda item: (item[1] == 0, item[0]))
        if count
    ]
    if rendered_reasons:
        for line in rendered_reasons:
            print(line)
    else:
        print("None")

    print()
    print("REQUIRES REVIEW")
    review_positions = [
        item for item in reconciliation.get("position_reconciliation", [])
        if isinstance(item, dict) and item.get("classification") == "UNMATCHED_REQUIRES_REVIEW"
    ]
    if review_positions:
        for position in review_positions:
            print(f"issuer: {position.get('issuer', '')}")
            print(f"product_code: {position.get('product_code', '')}")
            print(f"classification: {position.get('classification', '')}")
            print(f"series: {position.get('series', '')}")
            print(f"masked ISIN: {_redact_value(position.get('isin', ''))}")
            print(f"maturity_date: {position.get('maturity_date', '')}")
            print(f"market_value: {position.get('market_value', '')}")
            print(f"reason_no_match: {position.get('reason_no_match', '')}")
            print()
    else:
        print("None")

    print()
    print("COLLISION SUMMARY")
    print(f"total_vector_collisions: {reconciliation.get('vector_key_collisions', 0)}")
    print(f"collisions_affecting_portfolio: {reconciliation.get('collisions_affecting_portfolio', 0)}")
    collision_details = [item for item in reconciliation.get("collision_details", []) if isinstance(item, dict)]
    affected_collisions = [item for item in collision_details if item.get("uses_matched_master_position")]
    if affected_collisions:
        for item in affected_collisions:
            price_values = []
            yield_values = []
            affected_series = []
            collision_key = item.get("key")
            for record in payload.get("price_vector", {}).get("records", []):
                if not isinstance(record, dict):
                    continue
                record_key = _compose_report_key(record.get("series_or_security_code", ""), record.get("maturity_date_if_present"))
                if record_key != collision_key:
                    continue
                price_values.append(record.get("market_price"))
                yield_values.append(record.get("market_yield"))
            for position in payload.get("positions", []):
                if not isinstance(position, dict):
                    continue
                if _compose_report_key(position.get("series", ""), position.get("maturity_date")) != collision_key:
                    continue
                affected_series.append(str(position.get("series", "")))
            economically_identical = bool(item.get("true_duplicates") and not item.get("price_or_yield_differs"))
            print(f"key: {item.get('key', '')}")
            print(f"record_count: {item.get('number_of_records', 0)}")
            print(f"economically_identical: {'yes' if economically_identical else 'no'}")
            print(f"market_price values: {price_values}")
            print(f"market_yield values: {yield_values}")
            print(f"affected portfolio series: {', '.join(affected_series) if affected_series else 'None'}")
            print()
    else:
        print("None")

    if diagnostic_mode:
        expected_unmatched = [
            item for item in reconciliation.get("position_reconciliation", [])
            if isinstance(item, dict) and item.get("classification") == "UNMATCHED_EXPECTED"
        ]
        if expected_unmatched:
            print()
            print("EXPECTED UNMATCHED")
            for position in expected_unmatched:
                print(f"issuer: {position.get('issuer', '')}")
                print(f"product_code: {position.get('product_code', '')}")
                print(f"classification: {position.get('classification', '')}")
                print(f"series: {position.get('series', '')}")
                print(f"masked ISIN: {_redact_value(position.get('isin', ''))}")
                print(f"maturity_date: {position.get('maturity_date', '')}")
                print(f"market_value: {position.get('market_value', '')}")
                print(f"reason_no_match: {position.get('reason_no_match', '')}")
                print()


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
    trace_security = os.getenv("AIP_TRACE_SECURITY")
    _trace_security(payload, trace_security=trace_security)

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
    first_rejected_row = payload['portfolio_master'].get('diagnostics', {}).get('first_rejected_row')
    if first_rejected_row:
        print("First rejected row:")
        print(f"  row: {first_rejected_row.get('row')}")
        print(f"  raw_row_values: {first_rejected_row.get('raw_row_values')}")
        print(f"  required_fields: {first_rejected_row.get('required_fields')}")
        print(f"  validation_result: {first_rejected_row.get('validation_result')}")
        print(f"  rejection_reason: {first_rejected_row.get('rejection_reason')}")
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
    match_summary = _extract_match_summary(payload)
    print(f"Positions: {len(payload.get('positions', []))}")
    print(f"Matched by ISIN: {match_summary.get('exact_isin_matches', 0)}")
    print(f"Matched by series/maturity: {match_summary.get('series_maturity_matches', 0)}")
    print(f"Matched by issuer/product/maturity: {match_summary.get('issuer_product_maturity_matches', 0)}")
    print(f"Ambiguous: {match_summary.get('ambiguous_matches', 0)}")
    print(f"Unmatched: {match_summary.get('unmatched_positions', 0)}")
    print(f"Match percentage: {match_summary.get('match_percentage', 0.0)}")
    print(f"vector_records_available_for_matching: {payload['price_vector'].get('accepted_count', 0)}")
    print(f"vector_keys_generated: {match_summary.get('vector_keys_generated', 0)}")
    print(f"vector_key_collisions: {match_summary.get('vector_key_collisions', 0)}")
    vector_key_sample = match_summary.get('vector_key_sample') or {}
    if isinstance(vector_key_sample, dict):
        print(f"vector_key_sample: {vector_key_sample}")
    master_key_sample = match_summary.get('master_key_sample') or {}
    if isinstance(master_key_sample, dict):
        print(f"master_key_sample: {master_key_sample}")
    lookup_result = match_summary.get('lookup_result') or {}
    if isinstance(lookup_result, dict):
        print(f"lookup_result: {lookup_result}")
    if payload.get('positions'):
        print("Position diagnostics:")
        for position in payload['positions'][:3]:
            diagnostics = position.get('matching_diagnostics', {})
            print(
                "  - line {line}: isin={isin} series={series} maturity={maturity} issuer={issuer} product={product} keys={keys}".format(
                    line=position.get('source_row', 'N/A'),
                    isin=_redact_value(position.get('isin', '')),
                    series=position.get('series', ''),
                    maturity=position.get('maturity_date', ''),
                    issuer=position.get('issuer', ''),
                    product=position.get('product_code', ''),
                    keys=diagnostics.get('matching_keys', {}),
                )
            )
    _print_reconciliation_sections(payload, match_summary, diagnostic_mode=source_config.resolve_diagnostic_mode())
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
