from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
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
            authentication_mode=source_config_payload.get("sql_server", {}).get(
                "authentication_mode", "windows"
            ),
            view=source_config_payload.get("sql_server", {}).get("view", "VISTA_1514_1515_1516"),
            scenario_filters=tuple(
                source_config_payload.get("sql_server", {}).get("scenario_filters", ())
            ),
        ),
        folder_watch=FolderWatchSourceConfig(
            enabled=bool(source_config_payload.get("folder_watch", {}).get("enabled", False)),
            portfolio_root=source_config_payload.get("folder_watch", {}).get("portfolio_root"),
            icl_root=source_config_payload.get("folder_watch", {}).get("icl_root"),
            curves_path=source_config_payload.get("folder_watch", {}).get("curves_path"),
            vector_path=source_config_payload.get("folder_watch", {}).get("vector_path"),
            portfolio_master_pattern=source_config_payload.get("folder_watch", {}).get(
                "portfolio_master_pattern", r"Inversiones\{year}\maestro\{month}\*.xls*"
            ),
            icl_file_pattern=source_config_payload.get("folder_watch", {}).get(
                "icl_file_pattern", r"ICL\Reportes ICL\*"
            ),
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
            directory_aliases=tuple(
                source_config_payload.get("vector", {}).get("directory_aliases", ())
            ),
            file_pattern=source_config_payload.get("vector", {}).get("file_pattern"),
            supported_extensions=tuple(
                source_config_payload.get("vector", {}).get("supported_extensions", ())
            ),
        ),
        bccr=BCCRSourceConfig(
            enabled=bool(source_config_payload.get("bccr", {}).get("enabled", False)),
            base_url=source_config_payload.get("bccr", {}).get("base_url"),
            timeout_seconds=float(
                source_config_payload.get("bccr", {}).get("timeout_seconds", 30.0)
            ),
            retries=int(source_config_payload.get("bccr", {}).get("retries", 3)),
            cache_enabled=bool(source_config_payload.get("bccr", {}).get("cache_enabled", True)),
        ),
        diagnostic_mode=bool(source_config_payload.get("diagnostic_mode", False)),
        metadata={
            "allow_prior_source_date": bool(
                source_config_payload.get("allow_prior_source_date", False)
            ),
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
    return format(
        value.quantize(Decimal("1" if decimals == 0 else f"1.{'0' * decimals}")), f",.{decimals}f"
    )


def _normalize_classification(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _normalize_lookup_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_position_value(position: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in position:
            value = position.get(key)
            if value not in (None, ""):
                return value

    source_values = position.get("source_values") or {}
    if not isinstance(source_values, dict):
        return None

    normalized_source_values = {
        _normalize_lookup_key(key): value for key, value in source_values.items()
    }
    for key in keys:
        normalized_key = _normalize_lookup_key(key)
        if normalized_key in normalized_source_values:
            value = normalized_source_values[normalized_key]
            if value not in (None, ""):
                return value
    return None


def _is_valid_rate(value: Any) -> bool:
    decimal_value = _coerce_decimal(value)
    return decimal_value != Decimal("0") and decimal_value.is_finite()


def _is_implausible_rate(value: Any) -> bool:
    decimal_value = _coerce_decimal(value)
    return abs(decimal_value) > Decimal("1000")


def _classify_rate_source(position: dict[str, Any]) -> tuple[str, Decimal | None, str, str, str]:
    classification = str(position.get("classification", "") or "")
    normalized_classification = _normalize_classification(classification)
    is_excluded = False
    exclusion_reason = ""
    if not normalized_classification:
        is_excluded = True
        exclusion_reason = "missing_classification"
    elif "cerrado" in normalized_classification or "closed" in normalized_classification:
        is_excluded = True
        exclusion_reason = "closed_position"

    master_tir = _resolve_position_value(
        position, "portfolio_yield", "yield_value", "master_tir", "tir"
    )
    facial_rate = _resolve_position_value(
        position, "nominal_rate", "facial_rate", "rate", "tasa nominal"
    )
    master_tir_value = _coerce_decimal(master_tir)
    facial_rate_value = _coerce_decimal(facial_rate)

    rate_source = "EXCLUDED"
    effective_rate: Decimal | None = None
    rate_detail = ""
    if is_excluded:
        return rate_source, effective_rate, "", exclusion_reason, ""

    if _is_valid_rate(master_tir_value):
        rate_source = "MASTER_TIR"
        effective_rate = master_tir_value
        rate_detail = "master_tir"
    elif _is_valid_rate(facial_rate_value):
        rate_source = "FACIAL_RATE_FALLBACK"
        effective_rate = facial_rate_value
        rate_detail = "facial_rate"
    else:
        rate_source = "MISSING_RATE_REVIEW"
        rate_detail = "missing_rate"

    if rate_source in {"MASTER_TIR", "FACIAL_RATE_FALLBACK"} and _is_implausible_rate(
        effective_rate
    ):
        rate_source = "MISSING_RATE_REVIEW"
        rate_detail = "implausible_rate"
    return rate_source, effective_rate, rate_detail, exclusion_reason, classification


def _read_master_positions(
    master_path: str | Path, *, cutoff_date: date, provider: ConfiguredPortfolioProvider
) -> list[dict[str, Any]]:
    reader = InstitutionalPortfolioMasterReader()
    read_result = reader.read(
        master_path, valuation_date_override=cutoff_date, diagnostic_mode=True
    )
    positions: list[dict[str, Any]] = []
    for raw_position in read_result.normalized_positions:
        source_values = raw_position.get("source_values", {}) or {}
        payload_position = {
            "isin": raw_position.get("isin", ""),
            "issuer": raw_position.get("issuer", ""),
            "series": raw_position.get("series", ""),
            "product_code": raw_position.get("product_code", ""),
            "currency": str(raw_position.get("currency", "USD")).upper(),
            "nominal": float(
                raw_position.get("traded_balance") or raw_position.get("principal_balance") or 0.0
            ),
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
        payload_position["source_values"] = {
            str(key): value for key, value in source_values.items()
        }
        positions.append(payload_position)
    return positions


def _read_vector_records(
    vector_path: str | Path, *, cutoff_date: date, provider: ConfiguredPortfolioProvider
) -> list[dict[str, Any]]:
    reader = InstitutionalPiPCAVectorReader()
    read_result = reader.read(vector_path, source_cutoff=cutoff_date, diagnostic_mode=True)
    return [provider._normalize_vector_record(record) for record in read_result.records]


def _build_tir_rows(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position in positions:
        classification = str(position.get("classification", "") or "")
        weight_value = _coerce_decimal(
            position.get("market_value_crc")
            or position.get("market_value")
            or position.get("book_value")
        )

        rate_source, effective_rate, _, exclusion_reason, _ = _classify_rate_source(position)
        master_tir = _resolve_position_value(
            position, "portfolio_yield", "yield_value", "master_tir", "tir"
        )
        facial_rate = _resolve_position_value(
            position, "nominal_rate", "facial_rate", "rate", "tasa nominal"
        )
        master_tir_value = _coerce_decimal(master_tir)
        facial_rate_value = _coerce_decimal(facial_rate)

        rows.append(
            {
                "source_row": position.get("source_row"),
                "issuer": position.get("issuer", ""),
                "isin": position.get("isin", ""),
                "series": position.get("series", ""),
                "product_code": position.get("product_code", ""),
                "currency": position.get("currency", ""),
                "classification": classification,
                "master_tir": master_tir_value,
                "facial_rate": facial_rate_value,
                "effective_rate": effective_rate,
                "rate_source": rate_source,
                "market_value_crc": _coerce_decimal(
                    position.get("market_value_crc") or position.get("market_value")
                ),
                "weighted_rate_contribution": (
                    effective_rate * weight_value
                    if rate_source in {"MASTER_TIR", "FACIAL_RATE_FALLBACK"}
                    and effective_rate is not None
                    else Decimal("0")
                ),
                "included_in_portfolio_tir": rate_source in {"MASTER_TIR", "FACIAL_RATE_FALLBACK"},
                "exclusion_reason": exclusion_reason,
            }
        )
    return rows


def _print_rate_bucket(label: str, rows: list[dict[str, Any]], *, rate_source: str) -> None:
    bucket_rows = [row for row in rows if row.get("rate_source") == rate_source]
    if not bucket_rows:
        print(f"{label}")
        print("  positions: 0")
        print("  CRC weight: 0.00")
        print("  weighted rate: 0.00")
        return
    total_weight = sum(
        (_coerce_decimal(row.get("market_value_crc")) for row in bucket_rows), Decimal("0")
    )
    weighted_rate = (
        sum(
            (
                _coerce_decimal(row.get("effective_rate"))
                * _coerce_decimal(row.get("market_value_crc"))
                for row in bucket_rows
            ),
            Decimal("0"),
        )
        / total_weight
        if total_weight
        else Decimal("0")
    )
    print(f"{label}")
    print(f"  positions: {len(bucket_rows)}")
    print(f"  CRC weight: {_format_decimal(total_weight)}")
    print(f"  weighted rate: {_format_decimal(weighted_rate)}")


def _print_excluded_summary(rows: list[dict[str, Any]]) -> None:
    excluded_rows = [row for row in rows if row.get("rate_source") == "EXCLUDED"]
    total_weight = sum(
        (_coerce_decimal(row.get("market_value_crc")) for row in excluded_rows), Decimal("0")
    )
    print("EXCLUDED")
    print(f"  positions: {len(excluded_rows)}")
    print(f"  CRC weight: {_format_decimal(total_weight)}")
    if excluded_rows:
        reasons = sorted(
            {
                row.get("exclusion_reason", "")
                for row in excluded_rows
                if row.get("exclusion_reason")
            }
        )
        print("  reasons: " + ", ".join(reasons))


def _print_rate_quality_diagnostics(rows: list[dict[str, Any]]) -> None:
    summary = {
        "null_master_tir": 0,
        "zero_master_tir": 0,
        "null_facial_rate": 0,
        "zero_facial_rate": 0,
        "implausible_rate": 0,
        "inconsistent_rate_scale": 0,
    }
    for row in rows:
        master_tir = row.get("master_tir")
        facial_rate = row.get("facial_rate")
        if master_tir is None:
            summary["null_master_tir"] += 1
        elif _coerce_decimal(master_tir) == Decimal("0"):
            summary["zero_master_tir"] += 1
        if facial_rate is None:
            summary["null_facial_rate"] += 1
        elif _coerce_decimal(facial_rate) == Decimal("0"):
            summary["zero_facial_rate"] += 1
        if _is_implausible_rate(master_tir) or _is_implausible_rate(facial_rate):
            summary["implausible_rate"] += 1
        if master_tir is not None and facial_rate is not None:
            master_value = _coerce_decimal(master_tir)
            facial_value = _coerce_decimal(facial_rate)
            if (
                master_value != Decimal("0")
                and facial_value != Decimal("0")
                and (
                    (abs(master_value) < Decimal("1") and abs(facial_value) > Decimal("1"))
                    or (abs(facial_value) < Decimal("1") and abs(master_value) > Decimal("1"))
                )
            ):
                summary["inconsistent_rate_scale"] += 1
    print("RATE QUALITY DIAGNOSTICS")
    for label, count in summary.items():
        print(f"  {label}: {count}")


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
        "master_tir",
        "facial_rate",
        "effective_rate",
        "rate_source",
        "market_value_crc",
        "weighted_rate_contribution",
        "included_in_portfolio_tir",
        "exclusion_reason",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        ""
                        if key
                        in {
                            "master_tir",
                            "facial_rate",
                            "effective_rate",
                            "market_value_crc",
                            "weighted_rate_contribution",
                        }
                        and value in {None, ""}
                        else (
                            _format_decimal(_coerce_decimal(value))
                            if key
                            in {
                                "master_tir",
                                "facial_rate",
                                "effective_rate",
                                "market_value_crc",
                                "weighted_rate_contribution",
                            }
                            else value
                        )
                    )
                    for key, value in row.items()
                    if key in fieldnames
                }
            )


def _print_report(rows: list[dict[str, Any]], *, output_path: Path, cutoff_date: date) -> None:
    print("TIR RECONCILIATION REPORT")
    print(f"Cutoff: {cutoff_date.isoformat()}")
    print(f"Output: {output_path}")
    print(f"Rows written: {len(rows)}")
    print()
    _print_rate_quality_diagnostics(rows)
    print()
    print("MASTER TIR SOURCE")
    _print_rate_bucket("MASTER TIR SOURCE", rows, rate_source="MASTER_TIR")
    print()
    print("FACIAL RATE FALLBACK")
    _print_rate_bucket("FACIAL RATE FALLBACK", rows, rate_source="FACIAL_RATE_FALLBACK")
    print()
    print("MISSING RATE REVIEW")
    missing_rows = [row for row in rows if row.get("rate_source") == "MISSING_RATE_REVIEW"]
    total_weight = sum(
        (_coerce_decimal(row.get("market_value_crc")) for row in missing_rows), Decimal("0")
    )
    print(f"  positions: {len(missing_rows)}")
    print(f"  CRC weight: {_format_decimal(total_weight)}")
    for row in missing_rows[:20]:
        print(
            f"    {row.get('issuer')} | {row.get('classification')} | {row.get('isin')} | crc={_format_decimal(_coerce_decimal(row.get('market_value_crc')))}"
        )
    print()
    _print_excluded_summary(rows)
    print()
    included_rows = [row for row in rows if row.get("included_in_portfolio_tir")]
    total_weight = sum(
        (_coerce_decimal(row.get("market_value_crc")) for row in included_rows), Decimal("0")
    )
    weighted_effective_tir = (
        sum(
            (
                _coerce_decimal(row.get("effective_rate"))
                * _coerce_decimal(row.get("market_value_crc"))
                for row in included_rows
            ),
            Decimal("0"),
        )
        / total_weight
        if total_weight
        else Decimal("0")
    )
    print("COMBINED PORTFOLIO TIR")
    print(f"  included positions: {len(included_rows)}")
    print(f"  CRC denominator: {_format_decimal(total_weight)}")
    print(f"  weighted effective TIR: {_format_decimal(weighted_effective_tir)}")
    print()
    print("BY CURRENCY")
    by_currency: dict[str, list[dict[str, Any]]] = {}
    for row in included_rows:
        by_currency.setdefault(
            str(row.get("currency", "")).strip().upper() or "UNKNOWN", []
        ).append(row)
    for currency, bucket_rows in sorted(by_currency.items()):
        bucket_weight = sum(
            (_coerce_decimal(row.get("market_value_crc")) for row in bucket_rows), Decimal("0")
        )
        print(f"  {currency}: positions={len(bucket_rows)} weight={_format_decimal(bucket_weight)}")
    print()
    print("BY ISSUER")
    by_issuer: dict[str, list[dict[str, Any]]] = {}
    for row in included_rows:
        by_issuer.setdefault(str(row.get("issuer", "")).strip() or "UNKNOWN", []).append(row)
    for issuer, bucket_rows in sorted(by_issuer.items()):
        bucket_weight = sum(
            (_coerce_decimal(row.get("market_value_crc")) for row in bucket_rows), Decimal("0")
        )
        print(f"  {issuer}: positions={len(bucket_rows)} weight={_format_decimal(bucket_weight)}")
    print()
    print("BY PRODUCT")
    by_product: dict[str, list[dict[str, Any]]] = {}
    for row in included_rows:
        by_product.setdefault(str(row.get("product_code", "")).strip() or "UNKNOWN", []).append(row)
    for product_code, bucket_rows in sorted(by_product.items()):
        bucket_weight = sum(
            (_coerce_decimal(row.get("market_value_crc")) for row in bucket_rows), Decimal("0")
        )
        print(
            f"  {product_code}: positions={len(bucket_rows)} weight={_format_decimal(bucket_weight)}"
        )
    print()
    print("BY CLASSIFICATION")
    by_classification: dict[str, list[dict[str, Any]]] = {}
    for row in included_rows:
        by_classification.setdefault(
            str(row.get("classification", "")).strip() or "UNKNOWN", []
        ).append(row)
    for classification, bucket_rows in sorted(by_classification.items()):
        bucket_weight = sum(
            (_coerce_decimal(row.get("market_value_crc")) for row in bucket_rows), Decimal("0")
        )
        print(
            f"  {classification}: positions={len(bucket_rows)} weight={_format_decimal(bucket_weight)}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a read-only TIR reconciliation diagnostic"
    )
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

    cutoff_date = (
        date.fromisoformat(args.cutoff_date) if args.cutoff_date else config.data_cutoff_date
    )
    provider = ConfiguredPortfolioProvider(config, source_config)

    if args.master_file and args.vector_file:
        positions = _read_master_positions(
            args.master_file, cutoff_date=cutoff_date, provider=provider
        )
        vector_records = _read_vector_records(
            args.vector_file, cutoff_date=cutoff_date, provider=provider
        )
    else:
        payload = provider.get_portfolio()
        positions = [
            dict(position)
            for position in payload.get("positions", [])
            if isinstance(position, dict)
        ]
        vector_records = []
        for record in payload.get("price_vector", {}).get("records", []):
            if isinstance(record, dict):
                vector_records.append(dict(record))

    service = InstitutionalPortfolioMatchingService()
    enriched_positions, _ = service.enrich_positions(
        positions, vector_records, diagnostic_mode=True
    )
    rows = _build_tir_rows(enriched_positions)

    output_path = Path(args.output).expanduser().resolve()
    _write_csv(rows, output_path)
    _print_report(rows, output_path=output_path, cutoff_date=cutoff_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
