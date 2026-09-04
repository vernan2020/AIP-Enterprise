from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.credit_quality import (
    CreditAgingAmount,
    CreditAgingBand,
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
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient


@dataclass(frozen=True, slots=True)
class SUGEFCreditQualityReadResult:
    lines: tuple[FinancialStatementLine, ...]
    endpoints: tuple[str, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _BucketRow:
    entity: FinancialEntity
    statement_date: date
    band: CreditAgingBand
    principal: Decimal
    source_row: int
    endpoint: str


class SUGEFCreditQualityReader:
    """Deriva indicadores 08ME14-01 desde el reporte oficial de días de atraso.

    SUGEF documenta siete códigos de atraso para la información posterior a
    enero de 2024: 1 al día; 2 de 1 a 30 días; 3 de 31 a 60; 4 de 61 a 90;
    5 de 91 a 180; 6 de 181 o más; y 7 cobro judicial. Este adaptador normaliza
    esas categorías y delega la aritmética al dominio.
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

    def read(self, cutoff_date: date) -> SUGEFCreditQualityReadResult:
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
                    regulation="1",
                    days_arrears="",
                )
                endpoints.add(response.endpoint)
                normalized = self._normalize_rows(response.rows, response.endpoint)
                if entity_code == "":
                    # El universo SFN vuelve a incluir las entidades consultadas
                    # directamente. Se excluyen solo esas entidades del scope SFN
                    # para evitar doble conteo, pero se conservan todas las filas
                    # legítimas de cada banda (por ejemplo, distintas monedas).
                    normalized = tuple(
                        row for row in normalized if row.entity.entity_id not in direct_entity_codes
                    )
                buckets.extend(normalized)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                scope = entity_code or "SFN completo"
                diagnostics.append(
                    f"SUGEF API ReporteDiasAtraso ({scope}): {type(exc).__name__}: {exc}"
                )

        lines, calc_diagnostics = self._calculate(tuple(buckets))
        diagnostics.extend(calc_diagnostics)
        if lines:
            diagnostics.append(
                "Indicadores de calidad de cartera calculados desde ReporteDiasAtraso "
                "SUGEF, sin completar bandas ausentes con cero ni descartar filas por moneda."
            )
        return SUGEFCreditQualityReadResult(
            lines=lines,
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

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
            result = self._calculator.calculate(
                tuple(CreditAgingAmount(row.band, row.principal) for row in entity_rows)
            )
            if not result.complete:
                if result.missing_bands:
                    missing = ", ".join(band.value for band in result.missing_bands)
                    diagnostics.append(
                        f"{entity.name} {statement_date:%d/%m/%Y}: calidad de cartera no "
                        f"calculada; faltan bandas SUGEF ({missing})."
                    )
                elif result.gross_direct_portfolio == Decimal("0"):
                    diagnostics.append(
                        f"{entity.name} {statement_date:%d/%m/%Y}: cartera directa total es cero."
                    )
                continue

            trace_row = min(entity_rows, key=lambda item: item.source_row)
            if result.current_portfolio is not None:
                lines.append(
                    self._indicator_line(
                        entity=entity,
                        statement_date=statement_date,
                        code="CURRENT_PORTFOLIO",
                        label="Cartera de crédito al día",
                        value=result.current_portfolio,
                        trace_row=trace_row,
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
                        formula="suma bandas atraso 5,6,7 / suma bandas atraso 1..7",
                    )
                )
        return tuple(lines), tuple(diagnostics)

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
            band = cls._BAND_BY_SUGEF_CODE.get(cls._identifier(row.get("maximoAtraso")))
            principal = cls._decimal(row.get("saldoPrincipal"))
            if not entity_id or not entity_name or statement_date is None or band is None:
                continue
            if principal is None:
                # Null significa no disponible; nunca se convierte a cero.
                continue
            result.append(
                _BucketRow(
                    entity=FinancialEntity(
                        entity_id=entity_id,
                        name=entity_name,
                        category=cls._text(row.get("nombreTipoEntidad")) or "Sin clasificar",
                    ),
                    statement_date=statement_date,
                    band=band,
                    principal=principal,
                    source_row=row_number,
                    endpoint=endpoint,
                )
            )
        return tuple(result)

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
                file_path=f"{trace_row.endpoint} · {formula}",
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
