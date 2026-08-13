from __future__ import annotations

import argparse
import csv
import re
import sys
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


def _normalize_classification(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _is_amortized_cost_classification(classification: str | None) -> bool:
    normalized = _normalize_classification(classification)
    return "amort" in normalized or "costo amortizado" in normalized


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
            "currency": str(raw_position.get("currency", "USD")).upper(),
            "nominal": float(raw_position.get("traded_balance") or raw_position.get("principal_balance") or 0.0),
            "market_value": float(raw_position.get("market_value", 0.0) or 0.0),
            "book_value": float(raw_position.get("book_value", 0.0) or 0.0),
            "yield_value": float(raw_position.get("portfolio_yield", 0.0) or 0.0),
            "classification": raw_position.get("classification", "Unknown"),
            "source_file": raw_position.get("source_file"),
            "source_row": raw_position.get("source_row"),
            "maturity_date": raw_position.get("maturity_date"),
            "source_values": source_values,
            "market_value_crc": float(raw_position.get("market_value_crc", 0.0) or 0.0),
            "principal_balance": float(raw_position.get("principal_balance", 0.0) or 0.0),
            "traded_balance": float(raw_position.get("traded_balance", 0.0) or 0.0),
            "portfolio_yield": float(raw_position.get("portfolio_yield", 0.0) or 0.0),
            "nominal_rate": float(raw_position.get("nominal_rate", 0.0) or 0.0),
            "liquidity_reserve_flag": raw_position.get("liquidity_reserve_flag", ""),
        }
        payload_position["source_values"] = {str(key): value for key, value in source_values.items()}
        positions.append(payload_position)
    return positions


def _read_vector_records(vector_path: str | Path, *, cutoff_date: date, provider: ConfiguredPortfolioProvider) -> list[dict[str, Any]]:
    reader = InstitutionalPiPCAVectorReader()
    read_result = reader.read(vector_path, source_cutoff=cutoff_date, diagnostic_mode=True)
    return [provider._normalize_vector_record(record) for record in read_result.records]


def _build_tir_rows(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position in positions:
        classification = str(position.get("classification", "") or "")
        is_amortized = _is_amortized_cost_classification(classification)
        weight_value = _coerce_decimal(position.get("market_value_crc") or position.get("market_value") or position.get("book_value"))
        rate_value = Decimal("0")
        rate_source = "none"
        if is_amortized:
            rate_value = _coerce_decimal(position.get("nominal_rate") or position.get("portfolio_yield") or position.get("yield_value"))
            rate_source = "nominal_rate" if _coerce_decimal(position.get("nominal_rate") or position.get("portfolio_yield") or position.get("yield_value")) != Decimal("0") else "portfolio_yield"
        else:
            rate_value = _coerce_decimal(position.get("portfolio_yield") or position.get("yield_value") or position.get("nominal_rate"))
            rate_source = "master_tir" if _coerce_decimal(position.get("portfolio_yield") or position.get("yield_value") or position.get("nominal_rate")) != Decimal("0") else "nominal_rate"

        is_excluded = False
        exclusion_reason = ""
        normalized_classification = _normalize_classification(classification)
        if not normalized_classification:
            is_excluded = True
            exclusion_reason = "missing_classification"
        elif "cerrado" in normalized_classification or "closed" in normalized_classification:
            is_excluded = True
            exclusion_reason = "closed_position"

        rows.append(
            {
                "source_row": position.get("source_row"),
                "issuer": position.get("issuer", ""),
                "isin": position.get("isin", ""),
                "series": position.get("series", ""),
                "product_code": position.get("product_code", ""),
                "currency": position.get("currency", ""),
                "classification": classification,
                "nominal": _coerce_decimal(position.get("nominal") or position.get("traded_balance") or position.get("principal_balance")),
                "book_value": _coerce_decimal(position.get("book_value")),
                "market_value": _coerce_decimal(position.get("market_value")),
                "market_value_crc": _coerce_decimal(position.get("market_value_crc") or position.get("market_value")),
                "weight_value": weight_value,
                "rate": rate_value,
                "rate_source": rate_source,
                "is_amortized_cost": is_amortized,
                "is_eligible": not is_excluded,
                "exclusion_reason": exclusion_reason,
            }
        )
    return rows


def _print_summary(label: str, rows: list[dict[str, Any]]) -> None:
    eligible_rows = [row for row in rows if row.get("is_eligible")]
    if not eligible_rows:
        print(f"{label}")
        print("  positions: 0")
        print("  total_weight: 0.00")
        print("  weighted_rate: 0.00")
        return
    total_weight = sum((_coerce_decimal(row.get("weight_value")) for row in eligible_rows), Decimal("0"))
    weighted_rate = sum((_coerce_decimal(row.get("rate")) * _coerce_decimal(row.get("weight_value")) for row in eligible_rows), Decimal("0")) / total_weight if total_weight else Decimal("0")
    print(f"{label}")
    print(f"  positions: {len(eligible_rows)}")
    print(f"  total_weight: {_format_decimal(total_weight)}")
    print(f"  weighted_rate: {_format_decimal(weighted_rate)}")


def _print_excluded_summary(rows: list[dict[str, Any]]) -> None:
    excluded_rows = [row for row in rows if not row.get("is_eligible")]
    total_weight = sum((_coerce_decimal(row.get("weight_value")) for row in excluded_rows), Decimal("0"))
    print("EXCLUDED SUMMARY")
    print(f"  positions: {len(excluded_rows)}")
    print(f"  total_weight: {_format_decimal(total_weight)}")
    if excluded_rows:
        print("  reasons: " + ", ".join(sorted({row.get("exclusion_reason", "") for row in excluded_rows if row.get("exclusion_reason")})))


def _write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_row",
        "issuer",
        "isin",
        "series",
        "product_code",
        "currency",
        "classification",
        "nominal",
        "book_value",
        "market_value",
        "market_value_crc",
        "weight_value",
        "rate",
        "rate_source",
        "is_amortized_cost",
        "is_eligible",
        "exclusion_reason",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: (
                    _format_decimal(_coerce_decimal(value))
                    if key in {"nominal", "book_value", "market_value", "market_value_crc", "weight_value", "rate"}
                    else value
                )
                for key, value in row.items()
            })


def _print_report(rows: list[dict[str, Any]], *, output_path: Path, cutoff_date: date) -> None:
    print("TIR RECONCILIATION REPORT")
    print(f"Cutoff: {cutoff_date.isoformat()}")
    print(f"Output: {output_path}")
    print(f"Rows written: {len(rows)}")
    print()
    print("MARKET-VALUED SUMMARY")
    market_rows = [row for row in rows if row.get("is_eligible") and not row.get("is_amortized_cost")]
    _print_summary("MARKET-VALUED SUMMARY", market_rows)
    print()
    print("AMORTIZED-COST SUMMARY")
    amortized_rows = [row for row in rows if row.get("is_eligible") and row.get("is_amortized_cost")]
    _print_summary("AMORTIZED-COST SUMMARY", amortized_rows)
    print()
    print("COMBINED ELIGIBLE FIXED INCOME SUMMARY")
    eligible_rows = [row for row in rows if row.get("is_eligible")]
    _print_summary("COMBINED ELIGIBLE FIXED INCOME SUMMARY", eligible_rows)
    print()
    _print_excluded_summary(rows)
    print()
    print("POSITION DETAIL")
    for row in rows:
        print(
            f"{row.get('issuer')} | {row.get('classification')} | weight={_format_decimal(_coerce_decimal(row.get('weight_value')))} | rate={_format_decimal(_coerce_decimal(row.get('rate')))} | source={row.get('rate_source')}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a read-only TIR reconciliation diagnostic")
    parser.add_argument("--output", default="portfolio_tir.csv", help="CSV output path")
    parser.add_argument("--master-file", help="Path to the portfolio master workbook")
    parser.add_argument("--vector-file", help="Path to the PiPCA vector file")
    parser.add_argument("--cutoff-date", help="Override cutoff date, format YYYY-MM-DD")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config, source_config = _build_config()
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"TIR RECONCILIATION DIAGNOSTIC\nERROR: {exc}")
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
    rows = _build_tir_rows(enriched_positions)

    output_path = Path(args.output).expanduser().resolve()
    _write_csv(rows, output_path)
    _print_report(rows, output_path=output_path, cutoff_date=cutoff_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
