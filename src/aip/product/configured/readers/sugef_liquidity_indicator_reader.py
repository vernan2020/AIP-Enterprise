from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.liquidity import (
    LiquidityCoverageCalculator,
    LiquidityCoverageInput,
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
from aip.product.configured.readers.sugef_trial_balance_reader import (
    SUGEFTrialBalanceLine,
    SUGEFTrialBalanceReader,
)


@dataclass(frozen=True, slots=True)
class SUGEFLiquidityIndicatorReadResult:
    lines: tuple[FinancialStatementLine, ...]
    source_files: tuple[str, ...]
    diagnostics: tuple[str, ...]


class SUGEFLiquidityIndicatorReader:
    """Reproduce el indicador de liquidez desde la Balanza de Comprobación SUGEF.

    El reporte masivo de Balanza de Comprobación es de "solo saldos reportados".
    Por ello, una cuenta ausente no se convierte a cero a partir del barrido SFN.
    Para una entidad que no logra resolver las cuatro cuentas, AIP ejecuta una
    consulta directa de la balanza completa. Solo si esa consulta oficial es
    exitosa, el denominador 21000000 existe con saldo válido y una cuenta del
    numerador sigue completamente ausente, esa ausencia se interpreta como saldo
    cero exclusivamente para el cálculo 08ME14-01. Una fila publicada con saldo
    nulo permanece N/D.
    """

    _COMPONENTS = ("11000000", "12000000", "12500000", "21000000")
    _NUMERATOR_COMPONENTS = ("11000000", "12000000", "12500000")
    _DENOMINATOR = "21000000"
    _MAX_DIRECT_WORKERS = 2

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        trial_balance_reader: SUGEFTrialBalanceReader | None = None,
        calculator: LiquidityCoverageCalculator | None = None,
    ) -> None:
        self._trial_balance = trial_balance_reader or SUGEFTrialBalanceReader(config)
        self._calculator = calculator or LiquidityCoverageCalculator()

    def read(
        self,
        cutoff_date: date,
        *,
        include_all_entities: bool = True,
        expected_entity_codes: tuple[str, ...] = (),
    ) -> SUGEFLiquidityIndicatorReadResult:
        raw = self._trial_balance.read(
            cutoff_date,
            include_all_entities=include_all_entities,
        )
        diagnostics = list(raw.diagnostics)
        endpoints = set(raw.endpoints)
        grouped = self._group_component_rows(raw.lines)

        output: list[FinancialStatementLine] = []
        resolved_entities: set[str] = set()
        unresolved_entities: set[str] = set()
        for (entity_code, statement_date), entity_rows in grouped.items():
            line = self._calculate_entity(
                entity_rows,
                statement_date=statement_date,
                diagnostics=diagnostics,
                allow_confirmed_absent_zero=False,
            )
            if line is None:
                unresolved_entities.add(entity_code)
                continue
            output.append(line)
            resolved_entities.add(entity_code)

        observed_entities = {
            line.entity_code for line in raw.lines if line.statement_date == cutoff_date
        }
        recovery_candidates = (
            set(expected_entity_codes) | observed_entities | unresolved_entities
        ) - resolved_entities
        recovery_candidates.discard("")

        if recovery_candidates:
            recovered = self._recover_entities(
                cutoff_date=cutoff_date,
                entity_codes=tuple(sorted(recovery_candidates)),
            )
            for entity_code, direct in recovered:
                endpoints.update(direct.endpoints)
                diagnostics.extend(direct.diagnostics)
                direct_grouped = self._group_component_rows(direct.lines)
                entity_keys = [
                    key
                    for key in direct_grouped
                    if key[0] == entity_code and key[1] == cutoff_date
                ]
                if not entity_keys:
                    diagnostics.append(
                        f"Entidad SUGEF {entity_code} {cutoff_date:%d/%m/%Y}: liquidez N/D; "
                        "la consulta directa de Balanza de Comprobación no devolvió "
                        "componentes utilizables."
                    )
                    continue
                direct_line: FinancialStatementLine | None = None
                for key in entity_keys:
                    direct_line = self._calculate_entity(
                        direct_grouped[key],
                        statement_date=cutoff_date,
                        diagnostics=diagnostics,
                        allow_confirmed_absent_zero=True,
                    )
                    if direct_line is not None:
                        break
                if direct_line is not None:
                    output.append(direct_line)
                    resolved_entities.add(entity_code)

        deduplicated = {
            (line.entity.entity_id, line.statement_date, line.account_code): line
            for line in output
        }
        final_output = tuple(
            sorted(
                deduplicated.values(),
                key=lambda line: (line.entity.name.casefold(), line.statement_date),
            )
        )
        if final_output:
            diagnostics.append(
                f"Liquidez 08ME14-01: {len(final_output)} entidades calculadas desde Balanza "
                "de Comprobación SUGEF con la fórmula oficial configurada."
            )
        return SUGEFLiquidityIndicatorReadResult(
            lines=final_output,
            source_files=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

    def _recover_entities(
        self,
        *,
        cutoff_date: date,
        entity_codes: tuple[str, ...],
    ) -> tuple[tuple[str, object], ...]:
        """Consulta directamente solo pares aún no resueltos, con concurrencia acotada."""

        if not entity_codes:
            return ()

        def load(entity_code: str):
            return self._trial_balance.read(
                cutoff_date,
                entity_codes=(entity_code,),
                include_all_entities=False,
            )

        results: list[tuple[str, object]] = []
        with ThreadPoolExecutor(
            max_workers=min(self._MAX_DIRECT_WORKERS, len(entity_codes))
        ) as executor:
            futures = {executor.submit(load, entity_code): entity_code for entity_code in entity_codes}
            for future in as_completed(futures):
                entity_code = futures[future]
                try:
                    results.append((entity_code, future.result()))
                except Exception as exc:
                    # El lector normalmente encapsula errores de transporte; esta
                    # protección preserva N/D si un adaptador inyectado falla.
                    results.append((entity_code, _FailedTrialBalanceReadResult(str(exc))))
        return tuple(sorted(results, key=lambda item: item[0]))

    @classmethod
    def _group_component_rows(
        cls,
        lines: tuple[SUGEFTrialBalanceLine, ...],
    ) -> dict[tuple[str, date], list[SUGEFTrialBalanceLine]]:
        grouped: dict[tuple[str, date], list[SUGEFTrialBalanceLine]] = defaultdict(list)
        for line in lines:
            if line.account_code in cls._COMPONENTS:
                grouped[(line.entity_code, line.statement_date)].append(line)
        return grouped

    def _calculate_entity(
        self,
        entity_rows: list[SUGEFTrialBalanceLine],
        *,
        statement_date: date,
        diagnostics: list[str],
        allow_confirmed_absent_zero: bool,
    ) -> FinancialStatementLine | None:
        if not entity_rows:
            return None
        entity = FinancialEntity(
            entity_id=entity_rows[0].entity_code,
            name=entity_rows[0].entity_name,
            category=entity_rows[0].sector_name or "Sin clasificar",
        )
        by_catalog: dict[str, list[SUGEFTrialBalanceLine]] = defaultdict(list)
        for row in entity_rows:
            by_catalog[row.catalog_type_code].append(row)

        complete_catalogs: list[
            tuple[str, dict[str, Decimal], list[SUGEFTrialBalanceLine], tuple[str, ...]]
        ] = []
        for catalog_code, catalog_rows in sorted(by_catalog.items()):
            balances: dict[str, Decimal] = {}
            confirmed_zero: list[str] = []
            ambiguous = False
            for account_code in self._COMPONENTS:
                matches = [row for row in catalog_rows if row.account_code == account_code]
                if len(matches) > 1:
                    ambiguous = True
                    break
                if len(matches) == 1:
                    if matches[0].ending_balance is None:
                        ambiguous = True
                        break
                    balances[account_code] = matches[0].ending_balance
                    continue
                if (
                    allow_confirmed_absent_zero
                    and account_code in self._NUMERATOR_COMPONENTS
                    and self._has_valid_denominator(catalog_rows)
                ):
                    balances[account_code] = Decimal("0")
                    confirmed_zero.append(account_code)
                    continue
                ambiguous = True
                break
            if not ambiguous:
                complete_catalogs.append(
                    (catalog_code, balances, catalog_rows, tuple(confirmed_zero))
                )

        if len(complete_catalogs) > 1:
            catalogs = ", ".join(item[0] for item in complete_catalogs)
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y}: liquidez no calculada; "
                f"más de un tipo de catálogo contiene componentes válidos ({catalogs})."
            )
            return None
        if not complete_catalogs:
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y}: liquidez N/D; se requieren "
                "las cuentas 11000000, 12000000, 12500000 y 21000000 dentro del mismo "
                "tipo de catálogo. Las ausencias solo se consideran cero tras consulta "
                "directa SUGEF y nunca cuando existe una fila con saldo nulo."
            )
            return None

        catalog_code, balances, catalog_rows, confirmed_zero = complete_catalogs[0]
        result = self._calculator.calculate(
            LiquidityCoverageInput(
                cash_and_due_from=balances["11000000"],
                investments=balances["12000000"],
                available_investments=balances["12500000"],
                public_obligations=balances["21000000"],
            )
        )
        if not result.complete or result.value is None:
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y}: liquidez N/D por "
                "denominador cero o insumos no válidos."
            )
            return None

        trace = min(catalog_rows, key=lambda item: item.source_row)
        if confirmed_zero:
            diagnostics.append(
                f"{entity.name} {statement_date:%d/%m/%Y}: consulta directa SUGEF "
                "confirmó que las cuentas "
                f"{', '.join(confirmed_zero)} no tienen saldo reportado; se usan como cero "
                "exclusivamente en el cálculo de liquidez."
            )
        return FinancialStatementLine(
            entity=entity,
            statement_date=statement_date,
            statement_type=FinancialStatementType.INDICATORS,
            account_code="CALC:LIQUIDITY_COVERAGE",
            account_name=(
                "Disponibilidades e Inversiones Disponibles / Obligaciones con el público"
            ),
            amount=result.value,
            currency="RATIO",
            trace=SourceTrace(
                source_name="Cálculo 08ME14-01 sobre Balanza de Comprobación SUGEF",
                source_url="https://www.sugef.fi.cr/Bccr.Sugef.Reportes_SitioWeb.API",
                file_path=(
                    f"{trace.endpoint} · catálogo {catalog_code} · "
                    "(11000000+12000000+12500000)/21000000"
                ),
                sheet_name="ReporteBalanzaComprobacionEntidad",
                row_number=trace.source_row,
            ),
        )

    @classmethod
    def _has_valid_denominator(cls, rows: list[SUGEFTrialBalanceLine]) -> bool:
        matches = [row for row in rows if row.account_code == cls._DENOMINATOR]
        return len(matches) == 1 and matches[0].ending_balance is not None


@dataclass(frozen=True, slots=True)
class _FailedTrialBalanceReadResult:
    """Conserva un fallo inesperado de un adaptador inyectado como diagnóstico N/D."""

    error: str
    lines: tuple[SUGEFTrialBalanceLine, ...] = ()
    endpoints: tuple[str, ...] = ()

    @property
    def diagnostics(self) -> tuple[str, ...]:
        return (f"Consulta directa de Balanza SUGEF falló: {self.error}",)
