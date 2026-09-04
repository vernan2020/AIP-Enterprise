from __future__ import annotations

from collections import defaultdict
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
    """Reproduce el indicador de liquidez desde la Balanza de Comprobación SUGEF."""

    _COMPONENTS = ("11000000", "12000000", "12500000", "21000000")

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
    ) -> SUGEFLiquidityIndicatorReadResult:
        raw = self._trial_balance.read(
            cutoff_date,
            include_all_entities=include_all_entities,
        )
        diagnostics = list(raw.diagnostics)
        grouped: dict[tuple[str, date], list[SUGEFTrialBalanceLine]] = defaultdict(list)
        for line in raw.lines:
            if line.account_code in self._COMPONENTS:
                grouped[(line.entity_code, line.statement_date)].append(line)

        output: list[FinancialStatementLine] = []
        for (_, statement_date), entity_rows in grouped.items():
            entity = FinancialEntity(
                entity_id=entity_rows[0].entity_code,
                name=entity_rows[0].entity_name,
                category=entity_rows[0].sector_name or "Sin clasificar",
            )
            by_catalog: dict[str, list[SUGEFTrialBalanceLine]] = defaultdict(list)
            for row in entity_rows:
                by_catalog[row.catalog_type_code].append(row)

            complete_catalogs: list[tuple[str, dict[str, Decimal], list[SUGEFTrialBalanceLine]]] = []
            for catalog_code, catalog_rows in sorted(by_catalog.items()):
                balances: dict[str, Decimal] = {}
                ambiguous = False
                for account_code in self._COMPONENTS:
                    matches = [row for row in catalog_rows if row.account_code == account_code]
                    if len(matches) != 1 or matches[0].ending_balance is None:
                        ambiguous = True
                        break
                    balances[account_code] = matches[0].ending_balance
                if not ambiguous:
                    complete_catalogs.append((catalog_code, balances, catalog_rows))

            if len(complete_catalogs) > 1:
                catalogs = ", ".join(item[0] for item in complete_catalogs)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y}: liquidez no calculada; "
                    f"más de un tipo de catálogo contiene las cuatro cuentas ({catalogs})."
                )
                continue
            if not complete_catalogs:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y}: liquidez N/D; se requieren "
                    "exactamente las cuentas 11000000, 12000000, 12500000 y 21000000 "
                    "con saldo no nulo dentro del mismo tipo de catálogo."
                )
                continue

            catalog_code, balances, catalog_rows = complete_catalogs[0]
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
                continue
            trace = min(catalog_rows, key=lambda item: item.source_row)
            output.append(
                FinancialStatementLine(
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
            )
        if output:
            diagnostics.append(
                f"Liquidez 08ME14-01: {len(output)} entidades calculadas desde Balanza "
                "de Comprobación SUGEF con la fórmula oficial configurada."
            )
        return SUGEFLiquidityIndicatorReadResult(
            lines=tuple(output),
            source_files=raw.endpoints,
            diagnostics=tuple(diagnostics),
        )
