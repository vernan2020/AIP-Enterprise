from __future__ import annotations

from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.models import FinancialStatementLine, FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFApiReadResult,
    SUGEFFinancialApiClient,
)


class SUGEFOfficialFinancialApiClient(SUGEFFinancialApiClient):
    """Gateway SUGEF estricto para estados oficiales y universo comparativo SFN.

    La entidad configurada se consulta de forma directa para Balance, Resultados
    e Indicadores. Antes de descargar historia y pares se resuelve el último corte
    contable completo disponible que no excede la fecha solicitada. El universo
    comparativo se consulta con ``codigoEntidad`` vacío y la historia de Balance
    se solicita mes a mes para preservar 12 observaciones por entidad.
    """

    _BALANCE_REPORT = (
        "ReporteBalanceSituacionAnalisisFinancieroEntidad",
        "listaBalanceSituacionAnalisisFinancieroEntidad",
        FinancialStatementType.BALANCE_SHEET,
    )
    _INCOME_REPORT = (
        "ReporteEstadoResultadosAnalisisFinancieroEntidad",
        "listaEstadoResultadosAnalisisFinancieroEntidad",
        FinancialStatementType.INCOME_STATEMENT,
    )
    _INDICATOR_REPORT = (
        "ReporteIndicadoresFinancierosEntidad",
        "listaIndicadoresFinancierosEntidad",
        FinancialStatementType.INDICATORS,
    )

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)

    def read(self, cutoff_date: date) -> SUGEFApiReadResult:
        lines: list[FinancialStatementLine] = []
        endpoints: set[str] = set()
        diagnostics: list[str] = []

        # Fase 0: confirmar un corte contable completo de la entidad principal.
        # Se sondea mes a mes para que un mes todavía no publicado por SUGEF no
        # invalide toda la lectura solicitada por el corte general de AIP.
        resolved_cutoff = self._resolve_primary_statement_cutoff(cutoff_date, diagnostics)

        # Fase 1: una vez resuelto el corte, descargar la historia necesaria de
        # las entidades configuradas sin incluir meses aún no utilizables.
        if resolved_cutoff is not None:
            primary_jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []
            for entity_code in self._config.api_entity_codes:
                primary_jobs.append(
                    (
                        entity_code,
                        self._period_range(
                            resolved_cutoff,
                            lookback_months=self._AVERAGE_LOOKBACK_MONTHS,
                        ),
                        *self._BALANCE_REPORT,
                    )
                )
                primary_jobs.append(
                    (
                        entity_code,
                        self._result_periods(resolved_cutoff),
                        *self._INCOME_REPORT,
                    )
                )
            self._execute_jobs(primary_jobs, lines, endpoints, diagnostics)

        effective_cutoff = self._primary_statement_cutoff(lines)
        if effective_cutoff is not None:
            effective_period = date(
                effective_cutoff.year,
                effective_cutoff.month,
                1,
            ).strftime("%Y%m%d")

            # Fase 2: indicadores directos de la entidad configurada. No se debe
            # depender de la consulta masiva del SFN para los valores propios.
            primary_indicator_jobs = [
                (entity_code, effective_period, *self._INDICATOR_REPORT)
                for entity_code in self._config.api_entity_codes
            ]
            self._execute_jobs(primary_indicator_jobs, lines, endpoints, diagnostics)

            # Fase 3: indicadores comparativos SFN en una llamada dedicada. Esta
            # consulta no compite con la descarga histórica de Balance/Resultados.
            self._execute_jobs(
                [("", effective_period, *self._INDICATOR_REPORT)],
                lines,
                endpoints,
                diagnostics,
            )

            # Fase 4: historia del universo SFN. Balance se obtiene mes a mes para
            # garantizar 12 observaciones por entidad y Resultados únicamente para
            # los períodos necesarios para la anualización móvil de 08ME14-01.
            peer_history_jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []
            peer_history_jobs.extend(
                ("", period, *self._BALANCE_REPORT)
                for period in self._peer_balance_periods(effective_cutoff)
            )
            peer_history_jobs.extend(
                ("", period, *self._INCOME_REPORT)
                for period in self._peer_income_periods(effective_cutoff)
            )
            self._execute_jobs(peer_history_jobs, lines, endpoints, diagnostics)

            # Algunas ejecuciones públicas aceptan el universo masivo de
            # indicadores pero no devuelven historia contable suficiente cuando
            # codigoEntidad está vacío. En ese caso se recupera exclusivamente la
            # historia faltante de las entidades ya descubiertas oficialmente en
            # el universo de indicadores. No se incorpora ninguna fuente alterna.
            self._recover_incomplete_peer_history(
                effective_cutoff,
                lines,
                endpoints,
                diagnostics,
            )

        lines = self._deduplicate(lines)
        lines = self._clip_to_primary_statement_cutoff(lines)
        effective_cutoff = self._primary_statement_cutoff(lines)
        if lines and effective_cutoff is not None:
            if effective_cutoff < cutoff_date:
                diagnostics.append(
                    "Corte solicitado en AIP: "
                    f"{cutoff_date.strftime('%d/%m/%Y')}; último corte contable SUGEF "
                    f"completo utilizable: {effective_cutoff.strftime('%d/%m/%Y')}."
                )
            else:
                diagnostics.append(
                    "Corte contable SUGEF completo confirmado: "
                    f"{effective_cutoff.strftime('%d/%m/%Y')}."
                )
            diagnostics.extend(
                (
                    "Balance y Estado de Resultados consultados exclusivamente en la API pública oficial de SUGEF.",
                    "Indicadores de la entidad seleccionada se consultan directamente en SUGEF; el universo comparativo SFN se consulta mediante codigoEntidad vacío en una llamada dedicada.",
                    "La historia comparativa de Balance se consulta mes a mes y Resultados por los períodos requeridos por 08ME14-01 para preservar 12 observaciones por entidad.",
                )
            )
        else:
            diagnostics.append("La API pública de SUGEF no devolvió registros utilizables.")

        return SUGEFApiReadResult(
            lines=tuple(lines),
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

    def _resolve_primary_statement_cutoff(
        self,
        requested_cutoff: date,
        diagnostics: list[str],
    ) -> date | None:
        if not self._config.api_entity_codes:
            diagnostics.append("No hay códigos de entidad SUGEF configurados.")
            return None

        primary = self._config.api_entity_codes[0]
        requested_month = date(requested_cutoff.year, requested_cutoff.month, 1)
        probe_failures: list[str] = []

        for offset in range(self._COMPARATIVE_LOOKBACK_MONTHS + 1):
            candidate = self._shift_month(requested_month, -offset)
            period = candidate.strftime("%Y%m%d")
            try:
                balance_lines, _ = self._read_report(
                    primary,
                    period,
                    *self._BALANCE_REPORT,
                )
                income_lines, _ = self._read_report(
                    primary,
                    period,
                    *self._INCOME_REPORT,
                )
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                probe_failures.append(
                    f"Sondeo SUGEF {candidate.strftime('%d/%m/%Y')}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            balance_dates = {
                line.statement_date
                for line in balance_lines
                if line.entity.entity_id == primary
                and line.statement_type is FinancialStatementType.BALANCE_SHEET
            }
            income_dates = {
                line.statement_date
                for line in income_lines
                if line.entity.entity_id == primary
                and line.statement_type is FinancialStatementType.INCOME_STATEMENT
            }
            common_dates = balance_dates & income_dates
            if common_dates:
                return max(common_dates)
            probe_failures.append(
                "Sondeo SUGEF "
                f"{candidate.strftime('%d/%m/%Y')}: no existe un corte común de Balance y Resultados."
            )

        diagnostics.append(
            "No se encontró un corte contable SUGEF completo (Balance + Estado de Resultados) "
            f"que no exceda {requested_cutoff.strftime('%d/%m/%Y')} dentro de la ventana de publicación."
        )
        diagnostics.extend(probe_failures)
        return None

    def _execute_jobs(
        self,
        jobs: list[tuple[str, str, str, str, FinancialStatementType]],
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        if not jobs:
            return
        with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as executor:
            futures = {
                executor.submit(
                    self._read_report,
                    entity_code,
                    period,
                    report_name,
                    list_key,
                    statement_type,
                ): (entity_code, report_name)
                for entity_code, period, report_name, list_key, statement_type in jobs
            }
            for future in as_completed(futures):
                entity_code, report_name = futures[future]
                try:
                    report_lines, endpoint = future.result()
                    lines.extend(report_lines)
                    endpoints.add(endpoint)
                except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                    scope = entity_code or "SFN completo"
                    diagnostics.append(
                        f"SUGEF API {report_name} ({scope}): " f"{type(exc).__name__}: {exc}"
                    )

    def _recover_incomplete_peer_history(
        self,
        cutoff_date: date,
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        primary_codes = set(self._config.api_entity_codes)
        peer_codes = sorted(
            {
                line.entity.entity_id
                for line in lines
                if line.statement_date == cutoff_date
                and line.statement_type is FinancialStatementType.INDICATORS
                and line.entity.entity_id not in primary_codes
            }
        )
        missing = tuple(
            code
            for code in peer_codes
            if not self._has_methodology_history(lines, code, cutoff_date)
        )
        if not missing:
            return

        jobs: list[tuple[str, str, str, str, FinancialStatementType]] = []
        balance_period = self._period_range(
            cutoff_date,
            lookback_months=self._AVERAGE_LOOKBACK_MONTHS,
        )
        income_period = self._result_periods(cutoff_date)
        for entity_code in missing:
            jobs.append((entity_code, balance_period, *self._BALANCE_REPORT))
            jobs.append((entity_code, income_period, *self._INCOME_REPORT))

        self._execute_jobs(jobs, lines, endpoints, diagnostics)
        recovered = sum(self._has_methodology_history(lines, code, cutoff_date) for code in missing)
        diagnostics.append(
            "Recuperación directa de historia SUGEF para comparables 08ME14-01: "
            f"{recovered}/{len(missing)} entidades con historia completa tras la recuperación."
        )

    @classmethod
    def _has_methodology_history(
        cls,
        lines: list[FinancialStatementLine],
        entity_code: str,
        cutoff_date: date,
    ) -> bool:
        balance_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == entity_code
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
            and line.statement_date <= cutoff_date
        }
        income_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == entity_code
            and line.statement_type is FinancialStatementType.INCOME_STATEMENT
            and line.statement_date <= cutoff_date
        }
        required_income_dates = {
            cutoff_date,
            cls._month_end_date(cutoff_date.year - 1, cutoff_date.month),
            cls._month_end_date(cutoff_date.year - 1, 12),
        }
        return (
            cutoff_date in balance_dates
            and len(balance_dates) >= cls._AVERAGE_LOOKBACK_MONTHS + 1
            and required_income_dates.issubset(income_dates)
        )

    @staticmethod
    def _month_end_date(year: int, month: int) -> date:
        return date(year, month, monthrange(year, month)[1])

    @classmethod
    def _peer_balance_periods(cls, cutoff_date: date) -> tuple[str, ...]:
        periods = tuple(
            cls._shift_month(date(cutoff_date.year, cutoff_date.month, 1), -offset)
            for offset in range(cls._AVERAGE_LOOKBACK_MONTHS + 1)
        )
        return tuple(f"{period:%Y%m%d}" for period in sorted(periods))

    @classmethod
    def _peer_income_periods(cls, cutoff_date: date) -> tuple[str, ...]:
        return tuple(part for part in cls._result_periods(cutoff_date).split(",") if part)

    @classmethod
    def _peer_periods(cls, cutoff_date: date) -> str:
        periods = tuple(
            cls._shift_month(date(cutoff_date.year, cutoff_date.month, 1), -offset)
            for offset in range(cls._COMPARATIVE_LOOKBACK_MONTHS + 1)
        )
        return ",".join(f"{period:%Y%m%d}" for period in sorted(periods))

    @staticmethod
    def _deduplicate(lines: list[FinancialStatementLine]) -> list[FinancialStatementLine]:
        unique: dict[
            tuple[str, date, FinancialStatementType, str, str],
            FinancialStatementLine,
        ] = {}
        for line in lines:
            key = (
                line.entity.entity_id,
                line.statement_date,
                line.statement_type,
                line.account_code,
                line.account_name,
            )
            # Las consultas directas de la entidad se ejecutan antes que las del
            # universo SFN; conservar la primera observación evita que una fila
            # masiva sustituya innecesariamente la trazabilidad directa.
            unique.setdefault(key, line)
        return list(unique.values())

    def _primary_statement_cutoff(
        self,
        lines: list[FinancialStatementLine],
    ) -> date | None:
        if not self._config.api_entity_codes:
            return None
        primary = self._config.api_entity_codes[0]
        balance_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
        }
        income_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_type is FinancialStatementType.INCOME_STATEMENT
        }
        common_dates = balance_dates & income_dates
        return max(common_dates) if common_dates else None

    def _clip_to_primary_statement_cutoff(
        self,
        lines: list[FinancialStatementLine],
    ) -> list[FinancialStatementLine]:
        """Evita que un indicador más reciente desplace el corte contable válido."""

        effective_cutoff = self._primary_statement_cutoff(lines)
        if effective_cutoff is None:
            return lines
        return [line for line in lines if line.statement_date <= effective_cutoff]
