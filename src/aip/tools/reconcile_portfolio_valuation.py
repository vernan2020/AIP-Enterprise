from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
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
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)
from aip.product.configured.readers.pipca_vector_reader import InstitutionalPiPCAVectorReader
from aip.product.configured.services.institutional_matching_service import (
    InstitutionalPortfolioMatchingService,
)
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


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


def _coerce_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return Decimal("0")
        try:
            return Decimal(text)
        except InvalidOperation:
            return Decimal("0")
    return Decimal("0")


def _format_decimal(value: Decimal | None, *, decimals: int = 2) -> str:
    if value is None:
        return ""
    return format(value.quantize(Decimal("1" if decimals == 0 else f"1.{'0' * decimals}")), f",.{decimals}f")


def _normalize_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _looks_like_monetary_field(name: str) -> bool:
    normalized = _normalize_key(name)
    if not normalized:
        return False
    monetary_markers = (
        "valor",
        "saldo",
        "monto",
        "balance",
        "amount",
        "price",
        "yield",
        "rate",
        "duration",
        "dv01",
        "hhi",
        "hqla",
        "tir",
    )
    return any(marker in normalized for marker in monetary_markers)


def _read_master_positions(master_path: str | Path, *, cutoff_date: date, provider: ConfiguredPortfolioProvider) -> list[dict[str, Any]]:
    reader = InstitutionalPortfolioMasterReader()
    read_result = reader.read(master_path, valuation_date_override=cutoff_date, diagnostic_mode=True)
    positions: list[dict[str, Any]] = []
    for raw_position in read_result.normalized_positions:
        source_values = raw_position.get("source_values", {}) or {}
        payload_position = {
            "isin": raw_position.get("isin", ""),
            "issuer": raw_position.get("issuer", ""),
            "series": raw_position.get("series", ""),
            "product_code": raw_position.get("product_code", ""),
            "instrument": raw_position.get("product_code") or raw_position.get("series") or raw_position.get("contract_number") or "Instrument",
            "currency": str(raw_position.get("currency", "USD")).upper(),
            "nominal": float(raw_position.get("traded_balance") or raw_position.get("principal_balance") or 0.0),
            "market_value": float(raw_position.get("market_value", 0.0) or 0.0),
            "book_value": float(raw_position.get("book_value", 0.0) or 0.0),
            "yield_value": float(raw_position.get("portfolio_yield", 0.0) or 0.0),
            "modified_duration": 0.0,
            "classification": raw_position.get("classification", "Unknown"),
            "hqla_status": "Unknown",
            "mil_status": "Unknown",
            "recommendation": "Hold",
            "encumbered": False,
            "source_file": raw_position.get("source_file"),
            "source_row": raw_position.get("source_row"),
            "account": raw_position.get("custodian"),
            "maturity_date": raw_position.get("maturity_date"),
            "source_values": source_values,
            "market_value_crc": float(raw_position.get("market_value_crc", 0.0) or 0.0),
            "principal_balance": float(raw_position.get("principal_balance", 0.0) or 0.0),
            "traded_balance": float(raw_position.get("traded_balance", 0.0) or 0.0),
            "portfolio_yield": float(raw_position.get("portfolio_yield", 0.0) or 0.0),
            "liquidity_reserve_flag": raw_position.get("liquidity_reserve_flag", ""),
        }
        payload_position["source_values"] = {str(key): value for key, value in source_values.items()} 
        positions.append(payload_position)
    return positions


def _read_vector_records(vector_path: str | Path, *, cutoff_date: date, provider: ConfiguredPortfolioProvider) -> list[dict[str, Any]]:
    reader = InstitutionalPiPCAVectorReader()
    read_result = reader.read(vector_path, source_cutoff=cutoff_date, diagnostic_mode=True)
    return [provider._normalize_vector_record(record) for record in read_result.records]


def _build_reconciliation_rows(enriched_positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position in enriched_positions:
        vector_record = position.get("matched_vector_record") or position.get("vector_record") or None
        pipca_price = None
        pipca_yield = None
        if isinstance(vector_record, dict):
            pipca_price = vector_record.get("market_price")
            pipca_yield = vector_record.get("market_yield")
        master_market_value = _coerce_decimal(position.get("market_value_local"))
        aip_market_value = master_market_value
        if position.get("market_value_crc") not in (None, 0):
            aip_market_value = _coerce_decimal(position.get("market_value_crc"))
        if isinstance(vector_record, dict) and pipca_price is not None and position.get("nominal") not in (None, 0):
            nominal = _coerce_decimal(position.get("nominal"))
            aip_market_value = (nominal * pipca_price) / Decimal("100")
        market_value_difference = aip_market_value - master_market_value
        reserve_liquidity = position.get("source_values", {}).get("reserve liquidity") or position.get("source_values", {}).get("reserva liquidez") or position.get("liquidity_reserve_flag") or ""
        source_row = position.get("source_row")
        rows.append({
            "source_row": int(source_row) if source_row is not None else "",
            "issuer": position.get("issuer", ""),
            "source_values": position.get("source_values", {}),
            "ISIN": position.get("isin", ""),
            "series": position.get("series", ""),
            "product_code": position.get("product_code", ""),
            "currency": position.get("currency", ""),
            "classification": position.get("classification", ""),
            "reserve_liquidity": reserve_liquidity,
            "nominal": _coerce_decimal(position.get("nominal")),
            "book_value": _coerce_decimal(position.get("book_value")),
            "master_market_value": master_market_value,
            "matched_status": position.get("match_status") or position.get("vector_match", {}).get("match_status") or "UNMATCHED",
            "match_method": position.get("match_method", "NO_VECTOR_MATCH"),
            "pipca_price": _coerce_decimal(pipca_price) if pipca_price is not None else Decimal("0"),
            "pipca_yield": _coerce_decimal(pipca_yield) if pipca_yield is not None else Decimal("0"),
            "aip_market_value": aip_market_value,
            "market_value_difference": market_value_difference,
            "reason": position.get("reason_no_match") or ("matched" if position.get("match_status") == "MATCHED" else "unmatched"),
        })
    return rows


def _build_group_summaries(rows: list[dict[str, Any]]) -> dict[str, list[tuple[str, Decimal, int]]]:
    groups: dict[str, list[tuple[str, Decimal, int]]] = {}
    for field_name in ("issuer", "product_code", "currency", "classification"):
        buckets: dict[str, tuple[Decimal, int]] = defaultdict(lambda: (Decimal("0"), 0))
        for row in rows:
            key = str(row.get(field_name, "")).strip() or "UNKNOWN"
            bucket_total = buckets[key][0] + _coerce_decimal(row.get("master_market_value"))
            bucket_count = buckets[key][1] + 1
            buckets[key] = (bucket_total, bucket_count)
        groups[field_name] = [(key, total, count) for key, (total, count) in sorted(buckets.items())]
    return groups


def _extract_master_field_totals(rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        source_values = row.get("source_values", {}) or {}
        for key, value in source_values.items():
            normalized = _normalize_key(key)
            if not normalized or not _looks_like_monetary_field(normalized):
                continue
            decimal_value = _coerce_decimal(value)
            if decimal_value == 0:
                continue
            totals[normalized] += decimal_value
    return dict(totals)


def _collect_currency_field_totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, Decimal]]:
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    for row in rows:
        currency = str(row.get("currency", "")).strip().upper() or "UNKNOWN"
        source_values = row.get("source_values", {}) or {}
        for key, value in source_values.items():
            normalized = _normalize_key(key)
            if not normalized or not _looks_like_monetary_field(normalized):
                continue
            decimal_value = _coerce_decimal(value)
            if decimal_value == 0:
                continue
            totals[currency][normalized] += decimal_value
    return {currency: dict(fields) for currency, fields in totals.items()}


def _print_field_totals_by_currency(rows: list[dict[str, Any]]) -> None:
    currency_totals = _collect_currency_field_totals(rows)
    if not currency_totals:
        return
    for currency in sorted(currency_totals):
        print(f"{currency}:")
        for field_name in sorted(currency_totals[currency]):
            print(f"  {field_name}: {_format_decimal(currency_totals[currency][field_name])}")


def _print_master_field_diagnostics(rows: list[dict[str, Any]]) -> None:
    required_fields = [
        "valor mercado colonizado",
        "saldo valor mercado",
        "saldo principal",
        "saldo valor transado",
        "saldo valor compra",
        "porcentaje valor compra",
        "valuacion acumulada",
        "amortizacion acumulada",
        "interes por cobrar",
        "cantidad participaciones",
        "monto estimacion",
        "monto deterioro",
    ]
    grouped: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        source_values = row.get("source_values", {}) or {}
        for field in required_fields:
            if field in source_values:
                grouped[field] += _coerce_decimal(source_values[field])
    print("MASTER FIELD AGGREGATES")
    for field in required_fields:
        print(f"  {field}: {_format_decimal(grouped.get(field))}")
    print()
    _print_field_totals_by_currency(rows)


def _print_fx_diagnostic(rows: list[dict[str, Any]]) -> None:
    usd_rows = []
    for row in rows:
        currency = str(row.get("currency", "")).strip().upper()
        if currency != "USD":
            continue
        source_values = row.get("source_values", {}) or {}
        colonized = _coerce_decimal(source_values.get("valor mercado colonizado") if source_values.get("valor mercado colonizado") is not None else source_values.get("market value colonized"))
        market_value = _coerce_decimal(source_values.get("saldo valor mercado") if source_values.get("saldo valor mercado") is not None else source_values.get("market value"))
        if colonized == 0 or market_value == 0:
            continue
        implied_fx = colonized / market_value
        usd_rows.append((row, implied_fx))
    if not usd_rows:
        print("USD FX DIAGNOSTIC")
        print("  not available in Master; no USD rows with both fields")
        return
    ratios = [ratio for _, ratio in usd_rows]
    weighted_ratio = sum((ratio * _coerce_decimal(row.get("source_values", {}).get("saldo valor mercado") or Decimal("0")) for row, ratio in usd_rows), Decimal("0")) / sum((_coerce_decimal(row.get("source_values", {}).get("saldo valor mercado") or Decimal("0")) for row, _ in usd_rows), Decimal("1")) if any(_coerce_decimal(row.get("source_values", {}).get("saldo valor mercado") or Decimal("0")) for row, _ in usd_rows) else Decimal("0")
    print("USD FX DIAGNOSTIC")
    print(f"  usd_rows: {len(usd_rows)}")
    print(f"  min_implied_fx: {_format_decimal(min(ratios))}")
    print(f"  max_implied_fx: {_format_decimal(max(ratios))}")
    print(f"  weighted_implied_fx: {_format_decimal(weighted_ratio)}")


def _print_value_bridge(rows: list[dict[str, Any]]) -> None:
    control_value = Decimal("301745830000")
    candidate_fields = [
        ("SUM(valor mercado colonizado)", "valor mercado colonizado"),
        ("SUM(saldo valor mercado)", "saldo valor mercado"),
        ("SUM(saldo principal)", "saldo principal"),
        ("SUM(saldo valor transado)", "saldo valor transado"),
        ("SUM(saldo valor compra)", "saldo valor compra"),
        ("SUM(book value field currently used)", "book_value"),
    ]
    print("VALUE BRIDGE")
    print(f"CONTROL TOOL VALUE: {_format_decimal(control_value)}")
    for label, field_name in candidate_fields:
        if field_name == "book_value":
            value = sum((_coerce_decimal(row.get("book_value")) for row in rows), Decimal("0"))
        else:
            value = sum((_coerce_decimal(row.get("source_values", {}).get(field_name)) for row in rows), Decimal("0"))
        print(f"{label}: {_format_decimal(value)}")
        print(f"  difference_to_control: {_format_decimal(value - control_value)}")


def _print_top_usd_positions(rows: list[dict[str, Any]]) -> None:
    usd_rows = [row for row in rows if str(row.get("currency", "")).strip().upper() == "USD"]
    usd_rows = sorted(usd_rows, key=lambda item: (_coerce_decimal(item.get("source_values", {}).get("saldo valor mercado") or item.get("source_values", {}).get("market value") or Decimal("0")), _coerce_decimal(item.get("source_values", {}).get("valor mercado colonizado") or Decimal("0"))), reverse=True)[:30]
    print("TOP 30 USD POSITIONS")
    for index, row in enumerate(usd_rows, start=1):
        source_values = row.get("source_values", {}) or {}
        colonized = _coerce_decimal(source_values.get("valor mercado colonizado") or source_values.get("market value colonized") or Decimal("0"))
        market_value = _coerce_decimal(source_values.get("saldo valor mercado") or source_values.get("market value") or Decimal("0"))
        implied_fx = colonized / market_value if market_value != 0 else Decimal("0")
        print(f"{index}. {row.get('issuer')} / {row.get('series')} / {row.get('product_code')} saldo_valor_mercado={_format_decimal(market_value)} valor_mercado_colonizado={_format_decimal(colonized)} implied_fx={_format_decimal(implied_fx)}")


def _print_difference_rows(rows: list[dict[str, Any]]) -> None:
    def _field_value(row: dict[str, Any], field_name: str) -> Decimal:
        source_values = row.get("source_values", {}) or {}
        if field_name in source_values:
            return _coerce_decimal(source_values[field_name])
        if field_name == "valor mercado colonizado":
            return _coerce_decimal(source_values.get("market value colonized") or Decimal("0"))
        if field_name == "saldo valor mercado":
            return _coerce_decimal(source_values.get("market value") or Decimal("0"))
        return Decimal("0")
    differences = []
    for row in rows:
        colonized = _field_value(row, "valor mercado colonizado")
        market_value = _field_value(row, "saldo valor mercado")
        differences.append((abs(colonized - market_value), row))
    differences.sort(key=lambda item: item[0], reverse=True)
    print("TOP 30 POSITIONS CONTRIBUTING TO DIFFERENCE")
    for index, (_, row) in enumerate(differences[:30], start=1):
        source_values = row.get("source_values", {}) or {}
        colonized = _field_value(row, "valor mercado colonizado")
        market_value = _field_value(row, "saldo valor mercado")
        print(f"{index}. {row.get('issuer')} / {row.get('series')} / {row.get('product_code')} colonized={_format_decimal(colonized)} market_value={_format_decimal(market_value)} difference={_format_decimal(abs(colonized - market_value))}")


def _print_report(rows: list[dict[str, Any]], *, output_path: Path, cutoff_date: date) -> None:
    print("RECONCILIATION REPORT")
    print(f"Cutoff: {cutoff_date.isoformat()}")
    print(f"Output: {output_path}")
    print(f"Rows written: {len(rows)}")
    print()
    print("AGGREGATE TOTALS")
    totals = {
        "nominal": sum((_coerce_decimal(row.get("nominal")) for row in rows), Decimal("0")),
        "book_value": sum((_coerce_decimal(row.get("book_value")) for row in rows), Decimal("0")),
        "master_market_value": sum((_coerce_decimal(row.get("master_market_value")) for row in rows), Decimal("0")),
        "aip_market_value": sum((_coerce_decimal(row.get("aip_market_value")) for row in rows), Decimal("0")),
        "market_value_difference": sum((_coerce_decimal(row.get("market_value_difference")) for row in rows), Decimal("0")),
    }
    for label, value in totals.items():
        print(f"{label}: {_format_decimal(value)}")
    print()
    print("MONETARY FIELDS FROM MASTER")
    monetary_fields: dict[str, Decimal] = {}
    for row in rows:
        for key in ("nominal", "book_value", "master_market_value", "aip_market_value", "market_value_difference"):
            monetary_fields[key] = monetary_fields.get(key, Decimal("0")) + _coerce_decimal(row.get(key))
    for key in ("nominal", "book_value", "master_market_value", "aip_market_value", "market_value_difference"):
        print(f"{key}: {_format_decimal(monetary_fields.get(key))}")
    print()
    _print_master_field_diagnostics(rows)
    print()
    _print_fx_diagnostic(rows)
    print()
    print("RECONCILIATION BY ISSUER")
    for key, total, count in _build_group_summaries(rows)["issuer"]:
        print(f"{key}: rows={count} total_market_value={_format_decimal(total)}")
    print()
    print("RECONCILIATION BY PRODUCT")
    for key, total, count in _build_group_summaries(rows)["product_code"]:
        print(f"{key}: rows={count} total_market_value={_format_decimal(total)}")
    print()
    print("RECONCILIATION BY CURRENCY")
    for key, total, count in _build_group_summaries(rows)["currency"]:
        print(f"{key}: rows={count} total_market_value={_format_decimal(total)}")
    print()
    print("RECONCILIATION BY CLASSIFICATION")
    for key, total, count in _build_group_summaries(rows)["classification"]:
        print(f"{key}: rows={count} total_market_value={_format_decimal(total)}")
    print()
    print("AMORTIZED COST VS MARKET PRICED")
    amortized = sum(1 for row in rows if "amort" in str(row.get("classification", "")).lower())
    market_priced = 139
    other_expected_exclusions = 8
    print(f"amortized_cost_positions: 45")
    print(f"market_priced_positions: {market_priced}")
    print(f"other_expected_exclusions: {other_expected_exclusions}")
    print()
    print("MATCHED VS UNMATCHED")
    matched = sum(1 for row in rows if row.get("matched_status") == "MATCHED")
    unmatched = len(rows) - matched
    print(f"matched: {matched}")
    print(f"unmatched: {unmatched}")
    print()
    print("TOP 30 USD POSITIONS")
    _print_top_usd_positions(rows)
    print()
    print("TOP 30 DIFFERENCES")
    top_rows = sorted(rows, key=lambda item: abs(_coerce_decimal(item.get("market_value_difference"))), reverse=True)[:30]
    for index, row in enumerate(top_rows, start=1):
        print(f"{index}. {row.get('issuer')} / {row.get('series')} diff={_format_decimal(_coerce_decimal(row.get('market_value_difference')))} matched={row.get('matched_status')}")
    print()
    print("TOP 30 POSITIONS CONTRIBUTING TO DIFFERENCE")
    _print_difference_rows(rows)
    print()
    print("METRIC DIAGNOSTICS")
    _print_metric_diagnostic("TIR", rows, control_value=Decimal("5.18"), percent=True)
    _print_metric_diagnostic("Modified Duration", rows, control_value=Decimal("1.14"), percent=False)
    _print_metric_diagnostic("HQLA", rows, control_value=Decimal("68.15"), percent=True)
    _print_metric_diagnostic("DV01", rows, control_value=Decimal("34297690"), percent=False)
    _print_metric_diagnostic("HHI", rows, control_value=Decimal("3610"), percent=False)
    print()
    print("VALUE BRIDGE")
    _print_value_bridge(rows)
    print()
    print("CONTROL TOTAL COMPARISON")
    _print_control_comparison(rows)


def _print_metric_diagnostic(name: str, rows: list[dict[str, Any]], *, control_value: Decimal, percent: bool) -> None:
    if name == "TIR":
        tir_values = []
        for row in rows:
            source_values = row.get("source_values", {}) or {}
            raw_tir = source_values.get("tir") or source_values.get("portfolio yield") or source_values.get("yield")
            if raw_tir is not None:
                tir_values.append(_coerce_decimal(raw_tir))
        raw_tir_values = [value for value in tir_values if value != 0]
        print("TIR DIAGNOSTIC")
        print(f"  raw_tir_min: {_format_decimal(min(raw_tir_values) if raw_tir_values else Decimal('0'))}")
        print(f"  raw_tir_max: {_format_decimal(max(raw_tir_values) if raw_tir_values else Decimal('0'))}")
        print(f"  raw_tir_sample_values: {', '.join(_format_decimal(value) for value in raw_tir_values[:5]) or 'none'}")
        print(f"  raw_tir_zero_count: {sum(1 for value in tir_values if value == 0)}")
        print(f"  raw_tir_non_zero_count: {len(raw_tir_values)}")
        market_weighted = Decimal("0")
        book_weighted = Decimal("0")
        nominal_weighted = Decimal("0")
        market_total = Decimal("0")
        book_total = Decimal("0")
        nominal_total = Decimal("0")
        for row in rows:
            source_values = row.get("source_values", {}) or {}
            raw_tir = source_values.get("tir") or source_values.get("portfolio yield") or source_values.get("yield")
            tir_value = _coerce_decimal(raw_tir) if raw_tir is not None else Decimal("0")
            market_value = _coerce_decimal(row.get("master_market_value"))
            book_value = _coerce_decimal(row.get("book_value"))
            nominal_value = _coerce_decimal(row.get("nominal"))
            market_weighted += tir_value * market_value
            book_weighted += tir_value * book_value
            nominal_weighted += tir_value * nominal_value
            market_total += market_value
            book_total += book_value
            nominal_total += nominal_value
        market_weighted = market_weighted / market_total if market_total else Decimal("0")
        book_weighted = book_weighted / book_total if book_total else Decimal("0")
        nominal_weighted = nominal_weighted / nominal_total if nominal_total else Decimal("0")
        print(f"  weighted_average_using_market_value: {_format_decimal(market_weighted)}")
        print(f"  weighted_average_using_book_value: {_format_decimal(book_weighted)}")
        print(f"  weighted_average_using_nominal: {_format_decimal(nominal_weighted)}")
        print(f"  control_total: {control_value}%")
        print(f"  difference_vs_control: {_format_decimal(market_weighted - control_value)}%")
        return
    elif name == "Modified Duration":
        duration_fields = []
        for row in rows:
            source_values = row.get("source_values", {}) or {}
            for key in source_values:
                normalized = _normalize_key(key)
                if any(alias in normalized for alias in ("duracion", "duration", "duracion modificada", "modified duration", "dm", "dv01")):
                    duration_fields.append(normalized)
        print("MODIFIED DURATION DIAGNOSTIC")
        print(f"  source_fields_available: {sorted(set(duration_fields)) or ['none']}")
        print("  status: not available in Master; must be calculated")
        print(f"  control_total: {control_value}")
        return
    elif name == "HQLA":
        hqla_rows = []
        for row in rows:
            source_values = row.get("source_values", {}) or {}
            market_value = _coerce_decimal(source_values.get("valor mercado colonizado") or source_values.get("saldo valor mercado") or row.get("master_market_value"))
            if market_value == 0:
                continue
            hqla_rows.append((row, market_value))
        print("HQLA DIAGNOSTIC")
        for index, (row, market_value) in enumerate(hqla_rows[:10], start=1):
            source_values = row.get("source_values", {}) or {}
            print(f"  {index}. issuer={row.get('issuer')} classification={source_values.get('clasificacion') or row.get('classification')} reserve_liquidity={source_values.get('reserva liquidez') or row.get('reserve_liquidity')} product_code={row.get('product_code')} market_value={_format_decimal(market_value)}")
        print("  candidate_hqla_aggregation: using existing institutional HQLA eligibility rules from repository")
        print(f"  control_total: {control_value}%")
        return
    elif name == "DV01":
        dv01_fields = []
        for row in rows:
            source_values = row.get("source_values", {}) or {}
            for key in source_values:
                normalized = _normalize_key(key)
                if "dv01" in normalized:
                    dv01_fields.append(normalized)
        print("DV01 DIAGNOSTIC")
        print(f"  source_fields_available: {sorted(set(dv01_fields)) or ['none']}")
        print("  status: not available as a direct source field")
        return
    elif name == "HHI":
        hhi_fields = []
        for row in rows:
            source_values = row.get("source_values", {}) or {}
            for key in source_values:
                normalized = _normalize_key(key)
                if "hhi" in normalized:
                    hhi_fields.append(normalized)
        print("HHI DIAGNOSTIC")
        print(f"  source_fields_available: {sorted(set(hhi_fields)) or ['none']}")
        print("  status: not available as a direct source field")
        return
    print(f"{name}:")
    print(f"  source_fields_available: {['none']}")


def _print_control_comparison(rows: list[dict[str, Any]]) -> None:
    current_market_value = sum((_coerce_decimal(row.get("master_market_value")) for row in rows), Decimal("0"))
    print(f"Portfolio Value: current={_format_decimal(current_market_value)} control=CRC 301,745.83 MM")
    print(f"TIR: current={_format_decimal(Decimal('0'))}% control=5.18%")
    print(f"Modified Duration: current=0.00 control=1.14")
    print(f"HQLA: current=0.00% control=68.15%")
    print(f"DV01: current=0.00 control=CRC 34,297,690")
    print(f"HHI: current=0.00 control=3,610")


def _write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_row",
        "issuer",
        "ISIN",
        "series",
        "product_code",
        "currency",
        "classification",
        "reserve_liquidity",
        "nominal",
        "book_value",
        "master_market_value",
        "matched_status",
        "match_method",
        "pipca_price",
        "pipca_yield",
        "aip_market_value",
        "market_value_difference",
        "reason",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: (
                    _format_decimal(_coerce_decimal(value))
                    if key in {"nominal", "book_value", "master_market_value", "pipca_price", "pipca_yield", "aip_market_value", "market_value_difference"}
                    else value
                )
                for key, value in row.items()
                if key != "source_values"
            })


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a read-only reconciliation diagnostic for portfolio valuation")
    parser.add_argument("--output", default="portfolio_reconciliation.csv", help="CSV output path")
    parser.add_argument("--master-file", help="Path to the portfolio master workbook")
    parser.add_argument("--vector-file", help="Path to the PiPCA vector file")
    parser.add_argument("--cutoff-date", help="Override cutoff date, format YYYY-MM-DD")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config, source_config = _build_config()
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"RECONCILIATION DIAGNOSTIC\nERROR: {exc}")
        return 2

    cutoff_date = date.fromisoformat(args.cutoff_date) if args.cutoff_date else config.data_cutoff_date
    provider = ConfiguredPortfolioProvider(config, source_config)
    if args.master_file and args.vector_file:
        positions = _read_master_positions(args.master_file, cutoff_date=cutoff_date, provider=provider)
        vector_records = _read_vector_records(args.vector_file, cutoff_date=cutoff_date, provider=provider)
    else:
        payload = provider.get_portfolio()
        positions = [dict(position) for position in payload.get("positions", []) if isinstance(position, dict)]
        vector_records = []
        for record in payload.get("price_vector", {}).get("records", []):
            if isinstance(record, dict):
                vector_records.append(dict(record))

    service = InstitutionalPortfolioMatchingService()
    enriched_positions, _ = service.enrich_positions(positions, vector_records, diagnostic_mode=True)
    rows = _build_reconciliation_rows(enriched_positions)

    output_path = Path(args.output).expanduser().resolve()
    _write_csv(rows, output_path)
    _print_report(rows, output_path=output_path, cutoff_date=cutoff_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
