from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation

from aip.domain.financial_analysis.models import (
    EntityFinancialSummary,
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialMetric,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.domain.financial_analysis.ratings import FinancialEntityRatingService


class FinancialAnalysisService:
    """Calcula indicadores comparables sin depender de archivos ni de la interfaz."""

    _ACCOUNT_TERMS = {
        "ASSETS": ("TOTAL ACTIVO", "ACTIVO TOTAL"),
        "LOANS": ("CARTERA DE CREDITO", "CREDITOS VIGENTES", "TOTAL CARTERA"),
        "LIABILITIES": ("TOTAL PASIVO", "PASIVO TOTAL"),
        "EQUITY": ("TOTAL PATRIMONIO", "PATRIMONIO TOTAL"),
        "NET_INCOME": (
            "RESULTADO DEL PERIODO",
            "RESULTADO NETO",
            "UTILIDAD NETA",
            "EXCEDENTE NETO",
        ),
        "ROA_PUBLISHED": ("ROA", "RENDIMIENTO SOBRE ACTIVO", "RENDIMIENTO SOBRE ACTIVOS"),
        "ROE_PUBLISHED": ("ROE", "RENDIMIENTO SOBRE PATRIMONIO"),
    }

    def build_snapshot(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        selected_entity_id: str | None = None,
        cutoff_date: date | None = None,
        diagnostics: tuple[str, ...] = (),
        source_files: tuple[str, ...] = (),
    ) -> FinancialAnalysisSnapshot:
        entities = self._entities(lines)
        dates = tuple(sorted({line.statement_date for line in lines}, reverse=True))
        effective_date = self._effective_date(dates, cutoff_date)
        selected = self._selected_entity(entities, selected_entity_id)

        if selected is None or effective_date is None:
            return FinancialAnalysisSnapshot(
                status="UNAVAILABLE",
                cutoff_date=effective_date,
                selected_entity=selected,
                entities=entities,
                available_dates=dates,
                diagnostics=diagnostics,
                source_files=source_files,
            )

        current = tuple(
            line
            for line in lines
            if line.entity.entity_id == selected.entity_id
            and line.statement_date == effective_date
        )
        previous_date = next((value for value in dates if value < effective_date), None)
        previous = tuple(
            line
            for line in lines
            if line.entity.entity_id == selected.entity_id
            and line.statement_date == previous_date
        )
        metrics = self._metrics(current, previous)
        peers = self._peer_summaries(lines, effective_date)
        rating = FinancialEntityRatingService().evaluate(
            lines,
            selected_entity_id=selected.entity_id,
            cutoff_date=effective_date,
        )
        statement_types = {line.statement_type for line in current}
        has_balance = FinancialStatementType.BALANCE_SHEET in statement_types
        has_income = FinancialStatementType.INCOME_STATEMENT in statement_types
        status = "AVAILABLE" if has_balance and has_income else "PARTIAL"
        coverage_diagnostics = list(diagnostics)
        if not has_balance:
            coverage_diagnostics.append(
                "Cobertura parcial: falta el Balance de Situación oficial de SUGEF "
                "para la entidad y el corte seleccionados."
            )
        if not has_income:
            coverage_diagnostics.append(
                "Cobertura parcial: falta el Estado de Resultados oficial de SUGEF "
                "para la entidad y el corte seleccionados."
            )
        return FinancialAnalysisSnapshot(
            status=status,
            cutoff_date=effective_date,
            selected_entity=selected,
            entities=entities,
            available_dates=dates,
            metrics=metrics,
            statement_lines=tuple(sorted(current, key=self._line_sort_key)),
            peer_summaries=peers,
            rating=rating,
            diagnostics=tuple(coverage_diagnostics),
            source_files=source_files,
        )

    @classmethod
    def _metrics(
        cls,
        current: tuple[FinancialStatementLine, ...],
        previous: tuple[FinancialStatementLine, ...],
    ) -> tuple[FinancialMetric, ...]:
        current_values = {
            code: cls._find_value(
                current,
                terms,
                allow_indicators=code in {"ROA_PUBLISHED", "ROE_PUBLISHED"},
            )
            for code, terms in cls._ACCOUNT_TERMS.items()
        }
        previous_values = {
            code: cls._find_value(
                previous,
                terms,
                allow_indicators=code in {"ROA_PUBLISHED", "ROE_PUBLISHED"},
            )
            for code, terms in cls._ACCOUNT_TERMS.items()
        }
        definitions = (
            ("ASSETS", "Activos", "CRC"),
            ("LOANS", "Cartera de crédito", "CRC"),
            ("LIABILITIES", "Pasivos", "CRC"),
            ("EQUITY", "Patrimonio", "CRC"),
            ("NET_INCOME", "Resultado neto", "CRC"),
        )
        metrics = [
            FinancialMetric(
                code=code,
                label=label,
                value=current_values[code][0],
                unit=unit,
                previous_value=previous_values[code][0],
                change_percent=cls._change_percent(current_values[code][0], previous_values[code][0]),
                source_account=current_values[code][1],
            )
            for code, label, unit in definitions
        ]
        assets = current_values["ASSETS"][0]
        equity = current_values["EQUITY"][0]
        result = current_values["NET_INCOME"][0]
        previous_assets = previous_values["ASSETS"][0]
        previous_equity = previous_values["EQUITY"][0]
        previous_result = previous_values["NET_INCOME"][0]
        roa = cls._published_percent(current_values["ROA_PUBLISHED"][0])
        roe = cls._published_percent(current_values["ROE_PUBLISHED"][0])
        previous_roa = cls._published_percent(previous_values["ROA_PUBLISHED"][0])
        previous_roe = cls._published_percent(previous_values["ROE_PUBLISHED"][0])
        metrics.extend(
            (
                FinancialMetric(
                    code="ROA",
                    label="ROA",
                    value=roa if roa is not None else cls._ratio_percent(result, assets),
                    unit="PERCENT",
                    previous_value=(
                        previous_roa
                        if previous_roa is not None
                        else cls._ratio_percent(previous_result, previous_assets)
                    ),
                    source_account=(
                        current_values["ROA_PUBLISHED"][1]
                        or "DERIVADO SIMPLE: resultado / activos"
                    ),
                ),
                FinancialMetric(
                    code="ROE",
                    label="ROE",
                    value=roe if roe is not None else cls._ratio_percent(result, equity),
                    unit="PERCENT",
                    previous_value=(
                        previous_roe
                        if previous_roe is not None
                        else cls._ratio_percent(previous_result, previous_equity)
                    ),
                    source_account=(
                        current_values["ROE_PUBLISHED"][1]
                        or "DERIVADO SIMPLE: resultado / patrimonio"
                    ),
                ),
            )
        )
        return tuple(metrics)

    @classmethod
    def _peer_summaries(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        cutoff_date: date,
    ) -> tuple[EntityFinancialSummary, ...]:
        grouped: dict[str, list[FinancialStatementLine]] = defaultdict(list)
        for line in lines:
            if line.statement_date == cutoff_date:
                grouped[line.entity.entity_id].append(line)
        summaries: list[EntityFinancialSummary] = []
        for entity_lines in grouped.values():
            data = tuple(entity_lines)
            values = {
                code: cls._find_value(
                    data,
                    terms,
                    allow_indicators=code in {"ROA_PUBLISHED", "ROE_PUBLISHED"},
                )[0]
                for code, terms in cls._ACCOUNT_TERMS.items()
            }
            values["ROA_PUBLISHED"] = cls._published_percent(values["ROA_PUBLISHED"])
            values["ROE_PUBLISHED"] = cls._published_percent(values["ROE_PUBLISHED"])
            summaries.append(
                EntityFinancialSummary(
                    entity=data[0].entity,
                    statement_date=cutoff_date,
                    assets=values["ASSETS"],
                    loans=values["LOANS"],
                    liabilities=values["LIABILITIES"],
                    equity=values["EQUITY"],
                    net_income=values["NET_INCOME"],
                    roa_percent=(
                        values["ROA_PUBLISHED"]
                        if values["ROA_PUBLISHED"] is not None
                        else cls._ratio_percent(values["NET_INCOME"], values["ASSETS"])
                    ),
                    roe_percent=(
                        values["ROE_PUBLISHED"]
                        if values["ROE_PUBLISHED"] is not None
                        else cls._ratio_percent(values["NET_INCOME"], values["EQUITY"])
                    ),
                )
            )
        return tuple(
            sorted(
                summaries,
                key=lambda item: (item.assets is not None, item.assets or Decimal("0")),
                reverse=True,
            )
        )

    @classmethod
    def _find_value(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        terms: tuple[str, ...],
        *,
        allow_indicators: bool = False,
    ) -> tuple[Decimal | None, str | None]:
        candidates: list[tuple[int, int, FinancialStatementLine]] = []
        for line in lines:
            if (
                line.statement_type is FinancialStatementType.INDICATORS
                and not allow_indicators
            ):
                continue
            normalized = cls._normalize(line.account_name)
            for term in terms:
                if normalized == term:
                    candidates.append((0, len(normalized), line))
                elif term in normalized:
                    candidates.append((1, len(normalized), line))
        if not candidates:
            return (None, None)
        selected = min(candidates, key=lambda item: (item[0], item[1], item[2].account_code))[2]
        return (selected.amount, selected.account_code or selected.account_name)

    @staticmethod
    def _published_percent(value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value * Decimal("100") if abs(value) <= Decimal("1") else value

    @staticmethod
    def _ratio_percent(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
        if numerator is None or denominator in {None, Decimal("0")}:
            return None
        try:
            return numerator / denominator * Decimal("100")
        except (DivisionByZero, InvalidOperation):
            return None

    @staticmethod
    def _change_percent(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
        if current is None or previous in {None, Decimal("0")}:
            return None
        try:
            return (current / previous - Decimal("1")) * Decimal("100")
        except (DivisionByZero, InvalidOperation):
            return None

    @staticmethod
    def _entities(lines: tuple[FinancialStatementLine, ...]) -> tuple[FinancialEntity, ...]:
        unique = {line.entity.entity_id: line.entity for line in lines}
        return tuple(sorted(unique.values(), key=lambda item: item.name.casefold()))

    @staticmethod
    def _effective_date(dates: tuple[date, ...], requested: date | None) -> date | None:
        if not dates:
            return None
        if requested is None:
            return dates[0]
        return next((value for value in dates if value <= requested), None)

    @staticmethod
    def _selected_entity(
        entities: tuple[FinancialEntity, ...], requested_id: str | None
    ) -> FinancialEntity | None:
        if not entities:
            return None
        if requested_id:
            match = next((item for item in entities if item.entity_id == requested_id), None)
            if match is not None:
                return match
        coopealianza = next(
            (item for item in entities if "COOPEALIANZA" in item.name.upper()), None
        )
        return coopealianza or entities[0]

    @staticmethod
    def _line_sort_key(line: FinancialStatementLine) -> tuple[str, str]:
        return (line.statement_type.value, line.account_code)

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )
