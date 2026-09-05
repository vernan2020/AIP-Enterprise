from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.financial_analysis.models import (
    FinancialAnalysisSnapshot,
    RatingDirection,
)
from aip.domain.financial_analysis.services import FinancialAnalysisService
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_official_financial_statement_reader import (
    SUGEFOfficialFinancialStatementReader,
)

_DEFAULT_ENTITY = "3004045138"


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD, por ejemplo 2026-07-31") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valida la calificación 08ME14-01 con las fuentes oficiales SUGEF "
            "y el mismo motor usado por AIP Enterprise."
        )
    )
    parser.add_argument(
        "--cutoff",
        type=_parse_date,
        default=date.today(),
        help="Corte solicitado en formato YYYY-MM-DD. Por defecto usa la fecha actual.",
    )
    parser.add_argument(
        "--entity",
        default=_DEFAULT_ENTITY,
        help=f"Código SUGEF de entidad. Por defecto {_DEFAULT_ENTITY} (Coopealianza).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite un JSON estable para automatización en lugar del reporte de texto.",
    )
    return parser


def _decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _display_value(value: Decimal | None, direction: RatingDirection | None = None) -> str:
    if value is None:
        return "N/D"
    if direction is RatingDirection.BINARY:
        return "Sí (1)" if value == Decimal("1") else "No (0)"
    return f"{value * Decimal('100'):,.3f}%"


def _payload(snapshot: FinancialAnalysisSnapshot, requested_cutoff: date) -> dict[str, Any]:
    rating = snapshot.rating
    entity = snapshot.selected_entity
    rating_payload: dict[str, Any] | None = None
    if rating is not None:
        rating_payload = {
            "status": rating.status,
            "methodology": rating.methodology_code,
            "version": rating.methodology_version,
            "effective_date": rating.effective_date.isoformat(),
            "coverage_percent": _decimal_string(rating.coverage_percent),
            "score": _decimal_string(rating.score),
            "grade": rating.grade,
            "indicators": [
                {
                    "code": item.code,
                    "label": item.label,
                    "dimension": item.dimension,
                    "direction": item.direction.value,
                    "value": _decimal_string(item.value),
                    "peer_count": item.peer_count,
                    "percentile_15": _decimal_string(item.percentile_15),
                    "midpoint": _decimal_string(item.midpoint),
                    "percentile_85": _decimal_string(item.percentile_85),
                    "level": item.level.value,
                    "contribution": _decimal_string(item.contribution),
                    "source": item.source_account,
                }
                for item in rating.indicators
            ],
            "dimensions": [
                {
                    "name": item.name,
                    "weight_percent": _decimal_string(item.weight_percent),
                    "score": _decimal_string(item.score),
                    "available_indicators": item.available_indicators,
                    "total_indicators": item.total_indicators,
                }
                for item in rating.dimensions
            ],
            "diagnostics": list(rating.diagnostics),
        }

    return {
        "requested_cutoff": requested_cutoff.isoformat(),
        "effective_accounting_cutoff": (
            snapshot.cutoff_date.isoformat() if snapshot.cutoff_date is not None else None
        ),
        "snapshot_status": snapshot.status,
        "entity": (
            {
                "id": entity.entity_id,
                "name": entity.name,
                "category": entity.category,
            }
            if entity is not None
            else None
        ),
        "source_files": list(snapshot.source_files),
        "rating": rating_payload,
        "reconciliation": [
            {
                "code": item.code,
                "label": item.label,
                "published_value": _decimal_string(item.published_value),
                "calculated_value": _decimal_string(item.calculated_value),
                "difference": _decimal_string(item.difference),
                "tolerance": _decimal_string(item.tolerance),
                "status": item.status.value,
                "published_source": item.published_source,
                "calculated_source": item.calculated_source,
            }
            for item in snapshot.indicator_reconciliations
        ],
        "diagnostics": list(snapshot.diagnostics),
    }


def _print_text(snapshot: FinancialAnalysisSnapshot, requested_cutoff: date) -> None:
    rating = snapshot.rating
    entity = snapshot.selected_entity
    print("=== AIP ENTERPRISE · VALIDACIÓN SUGEF 08ME14-01 ===")
    print(f"Corte solicitado: {requested_cutoff:%d/%m/%Y}")
    print(
        "Corte contable efectivo: "
        + (snapshot.cutoff_date.strftime("%d/%m/%Y") if snapshot.cutoff_date else "N/D")
    )
    print(
        "Entidad: "
        + (f"{entity.name} [{entity.entity_id}]" if entity is not None else "N/D")
    )
    print(f"Estado del snapshot: {snapshot.status}")
    print(f"Fuentes procesadas: {len(snapshot.source_files)}")

    if rating is None:
        print("Calificación: N/D")
    else:
        print(
            f"Calificación: {rating.status} · Cobertura {rating.coverage_percent:,.2f}% · "
            f"Puntaje {rating.score if rating.score is not None else 'N/D'} · "
            f"Nota {rating.grade or 'N/D'}"
        )
        print("\n--- 13 INDICADORES ---")
        for index, item in enumerate(rating.indicators, start=1):
            print(
                f"{index:02d}. {item.label}: {_display_value(item.value, item.direction)} · "
                f"Pares {item.peer_count if item.direction is not RatingDirection.BINARY else 'N/A'} · "
                f"Nivel {item.level.value} · "
                f"Aporte {item.contribution if item.contribution is not None else 'N/D'}"
            )
            print(f"    Fuente: {item.source_account or 'N/D'}")

    if snapshot.indicator_reconciliations:
        print("\n--- RECONCILIACIÓN PUBLICADO vs CALCULADO ---")
        for item in snapshot.indicator_reconciliations:
            print(
                f"{item.label}: publicado={_display_value(item.published_value)} · "
                f"calculado={_display_value(item.calculated_value)} · "
                f"diferencia={_display_value(item.difference)} · {item.status.value}"
            )

    diagnostics = [*snapshot.diagnostics]
    if rating is not None:
        diagnostics.extend(rating.diagnostics)
    if diagnostics:
        print("\n--- DIAGNÓSTICOS ---")
        for message in dict.fromkeys(diagnostics):
            print(f"- {message}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cutoff: date = args.cutoff
    entity_id = str(args.entity).strip()
    if not entity_id:
        print("Error: --entity no puede estar vacío.")
        return 1

    config = SUGEFFinancialSourceConfig(
        enabled=True,
        cache_enabled=False,
        api_enabled=True,
        api_entity_codes=(entity_id,),
    )
    reader = SUGEFOfficialFinancialStatementReader(config)
    result = reader.read(cutoff_date=cutoff)
    snapshot = FinancialAnalysisService().build_snapshot(
        result.lines,
        selected_entity_id=entity_id,
        cutoff_date=cutoff,
        diagnostics=result.diagnostics,
        source_files=result.source_files,
    )

    if args.json:
        print(json.dumps(_payload(snapshot, cutoff), ensure_ascii=False, indent=2))
    else:
        _print_text(snapshot, cutoff)

    if snapshot.status == "UNAVAILABLE" or snapshot.rating is None:
        return 1
    return 0 if snapshot.rating.status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
