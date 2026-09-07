from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.credit_quality import (
    CreditAgingAmount,
    CreditAgingBand,
    CreditQualityCalculation,
    CreditQualityIndicatorCalculator,
)
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import (
    SUGEFPublicApiClient,
    SUGEFPublicApiResponse,
)


@dataclass(frozen=True, slots=True)
class SUGEFCreditQualityReadResult:
    lines: tuple[FinancialStatementLine, ...]
    endpoints: tuple[str, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _BucketRow:
    entity: FinancialEntity
    statement_date: date
    normative: str
    band: CreditAgingBand
    principal: Decimal
    source_row: int
    endpoint: str


class SUGEFCreditQualityReader:
    """Deriva indicadores 08ME14-01 desde el reporte oficial de días de atraso.

    SUGEF documenta siete códigos de atraso para la información posterior a
    enero de 2024: 1 al día; 2 de 1 a 30 días; 3 de 31 a 60; 4 de 61 a 90;
    5 de 91 a 180; 6 de 181 o más; y 7 cobro judicial. El API también expone
    la normativa aplicable a cada porción de cartera.

    El barrido SFN puede omitir tanto bandas sin saldo como entidades completas.
    AIP no interpreta esas ausencias como cero de forma automática. Las entidades
    del universo financiero que no aparezcan en el barrido se reconsultan de
    forma directa; después, cada normativa incompleta se vuelve a consultar antes
    de considerar una banda omitida como saldo cero. Una fila publicada con saldo
    nulo o inválido siempre permanece no disponible.
    """

    _BAND_BY_SUGEF_CODE = {
        "1": CreditAgingBand.CURRENT,
        "2": CreditAgingBand.DAYS_1_30,
        "3": CreditAgingBand.DAYS_31_60,
        "4": CreditAgingBand.DAYS_61_90,
        "5": CreditAgingBand.DAYS_91_180,
        "6": CreditAgingBand.DAYS_181_PLUS,
        "7": CreditAgingBand.JUDICIAL_COLLECTION,
    }
    _SOURCE_NAME = "Cálculo 08ME14-01 sobre cartera crediticia SUGEF"
    _MAX_DIRECT_WORKERS = 2

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFPublicApiClient | None = None,
        calculator: CreditQualityIndicatorCalculator | None = None,
    ) -> None:
        self._config = config
        self._api = api_client or SUGEFPublicApiClient(config)
        self._calculator = calculator or CreditQualityIndicatorCalculator()

    def read(
        self,
        cutoff_date: date,
        *,
        expected_entity_codes: tuple[str, ...] = (),
    ) -> SUGEFCreditQualityReadResult:
        if cutoff_date < date(2024, 1, 1):
            return SUGEFCreditQualityReadResult(
                (),
                (),
                (
                    "Calidad de cartera SUGEF: para cortes anteriores a enero 2024 "
                    "debe utilizarse la familia histórica Hasta2023.",
                ),
            )
        period = date(cutoff_date.year, cutoff_date.month, 1).strftime("%Y%m%d")
        diagnostics: list[str] = []
        endpoints: set[str] = set()
        buckets: list[_BucketRow] = []
        direct_entity_codes = set(self._config.api_entity_codes)

        scopes = [*self._config.api_entity_codes, ""]
        for entity_code in dict.fromkeys(scopes):
            try:
                response = self._api.read_credit_report(
                    "ReporteDiasAtraso",
                    entity_code=entity_code,
                    sector_code="",
                    periods=period,
                    regulation="",
                    days_arrears="",
                )
                endpoints.add(response.endpoint)
                normalized = self._normalize_rows(response.rows, response.endpoint)
                if entity_code == "":
                    normalized = tuple(
                        row for row in normalized if row.entity.entity_id not in direct_entity_codes
                    )
                buckets.extend(normalized)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                scope = entity_code or "SFN completo"
                diagnostics.append(
                    f"SUGEF API ReporteDiasAtraso ({scope}): {type(exc).__name__}: {exc}"
                )

        buckets = list(
            self._recover_missing_entities(
                period=period,
                buckets=tuple(buckets),
                expected_entity_codes=expected_entity_codes,
                endpoints=endpoints,
                diagnostics=diagnostics,
            )
        )
        recovered_buckets = self._recover_incomplete_normatives(
            period=period,
            buckets=tuple(buckets),
            endpoints=endpoints,
            diagnostics=diagnostics,
        )
        lines, calc_diagnostics = self._calculate(recovered_buckets)
        diagnostics.extend(calc_diagnostics)
        if lines:
            diagnostics.append(
                "Indicadores de calidad de cartera calculados desde ReporteDiasAtraso "
                "SUGEF, validando por separado todas las normativas aplicables para cada "
                "entidad. Las bandas omitidas solo se consideran saldo cero después de una "
                "consulta directa y exitosa; los saldos nulos permanecen N/D."
            )
        return SUGEFCreditQualityReadResult(
            lines=lines,
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

    def _recover_missing_entities(
        self,
        *,
        period: str,
        buckets: tuple[_BucketRow, ...],
        expected_entity_codes: tuple[str, ...],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> tuple[_BucketRow, ...]:
        """Reconsulta pares financieros ausentes por completo del barrido SFN."""

        observed = {row.entity.entity_id for row in buckets}
        missing = tuple(
            sorted(code for code in set(expected_entity_codes) if code and code not in observed)
        )
        if not missing:
            return buckets

        def load(entity_code: str) -> SUGEFPublicApiResponse:
            return self._api.read_credit_report(
                "ReporteDiasAtraso",
                entity_code=entity_code,
                sector_code="",
                periods=period,
                regulation="",
                days_arrears="",
            )

        output = list(buckets)
        with ThreadPoolExecutor(
            max_workers=min(self._MAX_DIRECT_WORKERS, len(missing))
        ) as executor:
            futures = {executor.submit(load, entity_code): entity_code for entity_code in missing}
            for future in as_completed(futures):
                entity_code = futures[future]
                try:
                    response = future.result()
                except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                    diagnostics.append(
                        f"Entidad SUGEF {entity_code}: no fue posible recuperar directamente "
                        f"ReporteDiasAtraso; se conserva N/D. {type(exc).__name__}: {exc}"
                    )
                    continue
                endpoints.add(response.endpoint)
                normalized = tuple(
                    row
                    for row in self._normalize_rows(response.rows, response.endpoint)
                    if row.entity.entity_id == entity_code
                )
                if not normalized:
                    diagnostics.append(
                        f"Entidad SUGEF {entity_code}: la consulta directa de "
                        "ReporteDiasAtraso no devolvió saldos principales válidos; "
                        "calidad de cartera permanece N/D."
                    )
                    continue
                output.extend(normalized)
                diagnostics.append(
                    f"Entidad SUGEF {entity_code}: calidad de cartera recuperada mediante "
                    "consulta directa porque el barrido SFN no contenía filas utilizables."
                )
        return tuple(output)

    def _recover_incomplete_normatives(
        self,
        *,
        period: str,
        buckets: tuple[_BucketRow, ...],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> tuple[_BucketRow, ...]:
        """Reconsulta normativas incompletas antes de interpretar bandas ausentes como cero."""

        grouped: dict[tuple[str, date, str], list[_BucketRow]] = defaultdict(list)
        for row in buckets:
            grouped[(row.entity.entity_id, row.statement_date, row.normative)].append(row)

        replacements: dict[tuple[str, date, str], tuple[_BucketRow, ...]] = {}
        for key, normative_rows in sorted(grouped.items()):
            entity_id, statement_date, normative = key
            initial = self._calculator.calculate(
                tuple(CreditAgingAmount(row.band, row.principal) for row in normative_rows)
            )
            if initial.complete or not initial.missing_bands:
                continue

            entity = normative_rows[0].entity
            try:
                response = self._api.read_credit_report(
                    "ReporteDiasAtraso",
                    entity_code=entity_id,
                    sector_code="",
                    periods=period,
                    regulation=normative,
                    days_arrears="",
                )
                endpoints.add(response.endpoint)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                missing = ", ".join(band.value for band in initial.missing_bands)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "no fue posible confirmar las bandas ausentes mediante consulta directa "
                    f"SUGEF ({missing}); se conserva N/D. {type(exc).__name__}: {exc}"
                )
                continue

            direct_rows = tuple(
                row
                for row in self._normalize_rows(response.rows, response.endpoint)
                if row.entity.entity_id == entity_id
                and row.statement_date == statement_date
                and row.normative == normative
            )
            if not direct_rows:
                missing = ", ".join(band.value for band in initial.missing_bands)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "la consulta directa SUGEF no devolvió filas válidas para confirmar "
                    f"las bandas ausentes ({missing}); se conserva N/D."
                )
                continue

            present_bands = {row.band for row in direct_rows}
            reported_bands = self._raw_reported_bands(
                response.rows,
                entity_id=entity_id,
                statement_date=statement_date,
                normative=normative,
            )
            missing_after_direct = tuple(
                band for band in CreditAgingBand if band not in present_bands
            )
            invalid_reported = tuple(
                band for band in missing_after_direct if band in reported_bands
            )
            confirmed_absent = tuple(
                band for band in missing_after_direct if band not in reported_bands
            )

            recovered = list(direct_rows)
            for band in confirmed_absent:
                recovered.append(
                    _BucketRow(
                        entity=direct_rows[0].entity,
                        statement_date=statement_date,
                        normative=normative,
                        band=band,
                        principal=Decimal("0"),
                        source_row=0,
                        endpoint=response.endpoint,
                    )
                )
            replacements[key] = tuple(recovered)

            if confirmed_absent:
                confirmed = ", ".join(band.value for band in confirmed_absent)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "consulta directa SUGEF confirmó ausencia de filas para las bandas "
                    f"{confirmed}; se registran con saldo cero exclusivamente para el cálculo."
                )
            if invalid_reported:
                invalid = ", ".join(band.value for band in invalid_reported)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "SUGEF sí reportó filas para las bandas "
                    f"{invalid}, pero el saldo principal es nulo o inválido; se conserva N/D."
                )
            if not confirmed_absent and not invalid_reported:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "consulta directa SUGEF recuperó todas las bandas de atraso faltantes."
                )

        if not replacements:
            return buckets

        output = [
            row
            for row in buckets
            if (row.entity.entity_id, row.statement_date, row.normative) not in replacements
        ]
        for key in sorted(replacements):
            output.extend(replacements[key])
        return tuple(output)

    def _calculate(
        self,
        buckets: tuple[_BucketRow, ...],
    ) -> tuple[tuple[FinancialStatementLine, ...], tuple[str, ...]]:
        grouped: dict[tuple[str, date], list[_BucketRow]] = defaultdict(list)
        for row in buckets:
            grouped[(row.entity.entity_id, row.statement_date)].append(row)

        lines: list[FinancialStatementLine] = []
        diagnostics: list[str] = []
        for (_, statement_date), entity_rows in grouped.items():
            entity = entity_rows[0].entity
            by_normative: dict[str, list[_BucketRow]] = defaultdict(list)
            for row in entity_rows:
                by_normative[row.normative].append(row)

            incomplete = False
            for normative, normative_rows in sorted(by_normative.items()):
                result = self._calculator.calculate(
                    tuple(CreditAgingAmount(row.band, row.principal) for row in normative_rows)
                )
                if result.complete:
                    continue
                incomplete = True
                self._append_incomplete_diagnostic(
                    diagnostics,
                    entity=entity,
                    statement_date=statement_date,
                    normative=normative,
                    result=result,
                )
            if incomplete:
                continue

            combined_rows = [
                row for normative in sorted(by_normative) for row in by_normative[normative]
            ]
            result = self._calculator.calculate(
                tuple(CreditAgingAmount(row.band, row.principal) for row in combined_rows)
            )
            if not result.complete:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y}: calidad de cartera N/D; "
                    "la agregación de normativas completas no produjo un resultado válido."
                )
                continue

            normative_labels = ", ".join(sorted(by_normative))
            if len(by_normative) > 1:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y}: calidad de cartera agregada "
                    f"sobre normativas SUGEF completas ({normative_labels}) para representar "
                    "la cartera total de la entidad."
                )
            source_rows = tuple(row for row in combined_rows if row.source_row > 0)
            trace_row = min(source_rows or tuple(combined_rows), key=lambda item: item.source_row)
            if result.current_portfolio is not None:
                lines.append(
                    self._indicator_line(
                        entity=entity,
                        statement_date=statement_date,
                        code="CURRENT_PORTFOLIO",
                        label="Cartera de crédito al día",
                        value=result.current_portfolio,
                        trace_row=trace_row,
                        normatives=normative_labels,
                        formula="banda atraso 1 / suma bandas atraso 1..7",
                    )
                )
            if result.delinquency_over_90 is not None:
                lines.append(
                    self._indicator_line(
                        entity=entity,
                        statement_date=statement_date,
                        code="DELINQUENCY_90",
                        label="Morosidad >90 días y cobro judicial / Cartera directa",
                        value=result.delinquency_over_90,
                        trace_row=trace_row,
                        normatives=normative_labels,
                        formula="suma bandas atraso 5,6,7 / suma bandas atraso 1..7",
                    )
                )
        return tuple(lines), tuple(diagnostics)

    @staticmethod
    def _append_incomplete_diagnostic(
        diagnostics: list[str],
        *,
        entity: FinancialEntity,
        statement_date: date,
        normative: str,
        result: CreditQualityCalculation,
    ) -> None:
        if result.missing_bands:
            missing = ", ".join(band.value for band in result.missing_bands)
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                f"calidad de cartera no calculada; faltan bandas SUGEF ({missing})."
            )
        elif result.gross_direct_portfolio == Decimal("0"):
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                "cartera directa total es cero."
            )
        else:
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                "calidad de cartera no calculada por insumos no válidos."
            )

    @classmethod
    def _normalize_rows(
        cls,
        rows: tuple[Mapping[str, Any], ...],
        endpoint: str,
    ) -> tuple[_BucketRow, ...]:
        result: list[_BucketRow] = []
        for row_number, row in enumerate(rows, start=1):
            entity_id = cls._text(row.get("codigoEntidad"))
            entity_name = cls._text(row.get("aliasPublicacionEntidad"))
            statement_date = cls._month_end(row.get("periodo"))
            normative = cls._identifier(row.get("normativa"))
            band = cls._BAND_BY_SUGEF_CODE.get(cls._identifier(row.get("maximoAtraso")))
            principal = cls._decimal(row.get("saldoPrincipal"))
            if (
                not entity_id
                or not entity_name
                or statement_date is None
                or not normative
                or band is None
            ):
                continue
            if principal is None:
                continue
            result.append(
                _BucketRow(
                    entity=FinancialEntity(
                        entity_id=entity_id,
                        name=entity_name,
                        category=cls._text(row.get("nombreTipoEntidad")) or "Sin clasificar",
                    ),
                    statement_date=statement_date,
                    normative=normative,
                    band=band,
                    principal=principal,
                    source_row=row_number,
                    endpoint=endpoint,
                )
            )
        return tuple(result)

    @classmethod
    def _raw_reported_bands(
        cls,
        rows: tuple[Mapping[str, Any], ...],
        *,
        entity_id: str,
        statement_date: date,
        normative: str,
    ) -> set[CreditAgingBand]:
        """Return bands explicitly present in the raw API response, including null balances."""

        reported: set[CreditAgingBand] = set()
        for row in rows:
            if cls._text(row.get("codigoEntidad")) != entity_id:
                continue
            if cls._month_end(row.get("periodo")) != statement_date:
                continue
            if cls._identifier(row.get("normativa")) != normative:
                continue
            band = cls._BAND_BY_SUGEF_CODE.get(cls._identifier(row.get("maximoAtraso")))
            if band is not None:
                reported.add(band)
        return reported

    @classmethod
    def _indicator_line(
        cls,
        *,
        entity: FinancialEntity,
        statement_date: date,
        code: str,
        label: str,
        value: Decimal,
        trace_row: _BucketRow,
        normatives: str,
        formula: str,
    ) -> FinancialStatementLine:
        return FinancialStatementLine(
            entity=entity,
            statement_date=statement_date,
            statement_type=FinancialStatementType.INDICATORS,
            account_code=f"CALC:{code}",
            account_name=label,
            amount=value,
            currency="RATIO",
            trace=SourceTrace(
                source_name=cls._SOURCE_NAME,
                source_url="https://www.sugef.fi.cr/Bccr.Sugef.Reportes_SitioWeb.API",
                file_path=f"{trace_row.endpoint} · normativas {normatives} · {formula}",
                sheet_name="ReporteDiasAtraso",
                row_number=trace_row.source_row,
            ),
        )

    @staticmethod
    def _month_end(value: Any) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None
        return date(parsed.year, parsed.month, monthrange(parsed.year, parsed.month)[1])

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _identifier(cls, value: Any) -> str:
        text = cls._text(value)
        return text[:-2] if text.endswith(".0") and text[:-2].isdigit() else text
