from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)


class OfficialRatingIndicatorCalculator:
    """Deriva indicadores de 08ME14-01 desde saldos oficiales de SUGEF."""

    _ASSETS = "10000"
    _EQUITY = "25000"
    _INTERMEDIATION_RESULT = "31300"
    _GROSS_OPERATING_RESULT = "31000"
    _ADMIN_EXPENSE = "32000"
    _FINAL_RESULT = "30000"
    _AVERAGE_MONTHS = 12

    _DEFINITIONS = (
        (
            "MARGIN_INTERMEDIATION",
            "Margen de Intermediación Financiera",
            _INTERMEDIATION_RESULT,
            _ASSETS,
        ),
        ("ROA", "ROA", _FINAL_RESULT, _ASSETS),
        ("ROE", "ROE", _FINAL_RESULT, _EQUITY),
        (
            "OPERATING_EFFICIENCY",
            "Eficiencia Operativa",
            _ADMIN_EXPENSE,
            _GROSS_OPERATING_RESULT,
        ),
        (
            "ADMIN_EXPENSE_ASSETS",
            "Gasto Administrativo sobre Activos",
            _ADMIN_EXPENSE,
            _ASSETS,
        ),
    )

    def augment(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
    ) -> tuple[FinancialStatementLine, ...]:
        derived: list[FinancialStatementLine] = []
        by_entity: dict[str, list[FinancialStatementLine]] = defaultdict(list)
        for line in lines:
            if line.statement_date <= cutoff_date:
                by_entity[line.entity.entity_id].append(line)
        for entity_lines in by_entity.values():
            derived.extend(self._derive_entity(tuple(entity_lines), cutoff_date=cutoff_date))
        return (*lines, *derived)

    def _derive_entity(
        self,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
    ) -> tuple[FinancialStatementLine, ...]:
        current = tuple(line for line in lines if line.statement_date == cutoff_date)
        if not current:
            return ()
        entity = current[0].entity
        results = self._dated_results(lines, cutoff_date=cutoff_date)
        monthly_balances = self._monthly_balances(lines, cutoff_date=cutoff_date)
        output: list[FinancialStatementLine] = []
        for code, label, numerator_code, denominator_code in self._DEFINITIONS:
            numerator = results.get(numerator_code, {}).get(cutoff_date)
            if numerator is None:
                continue
            if denominator_code in {self._ASSETS, self._EQUITY}:
                denominator = self._average(monthly_balances.get(denominator_code, ()))
                denominator_label = f"promedio 12 meses {denominator_code}"
            else:
                denominator = self._annualized_result(
                    results.get(denominator_code, {}), cutoff_date=cutoff_date
                )
                denominator_label = denominator_code
            numerator_value = self._annualized_result(
                results.get(numerator_code, {}), cutoff_date=cutoff_date
            )
            if numerator_value is None:
                continue
            value = self._ratio(numerator_value, denominator)
            if value is None:
                continue
            output.append(
                self._line(
                    entity=entity,
                    cutoff_date=cutoff_date,
                    code=code,
                    label=label,
                    value=value,
                    source=numerator,
                    formula=f"{numerator_code} / {denominator_label}",
                )
            )
        return tuple(output)

    @classmethod
    def _dated_results(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
    ) -> dict[str, dict[date, FinancialStatementLine]]:
        values: dict[str, dict[date, FinancialStatementLine]] = defaultdict(dict)
        for line in lines:
            if (
                line.statement_type is FinancialStatementType.INCOME_STATEMENT
                and line.statement_date <= cutoff_date
            ):
                values[cls._code(line)][line.statement_date] = line
        return values

    @staticmethod
    def _annualized_result(
        values: dict[date, FinancialStatementLine],
        *,
        cutoff_date: date,
    ) -> Decimal | None:
        current = values.get(cutoff_date)
        if current is None:
            return None
        if cutoff_date.month == 12:
            return current.amount
        prior_same_month = values.get(
            date(
                cutoff_date.year - 1,
                cutoff_date.month,
                monthrange(cutoff_date.year - 1, cutoff_date.month)[1],
            )
        )
        prior_december = values.get(date(cutoff_date.year - 1, 12, 31))
        if prior_same_month is None or prior_december is None:
            return None
        return current.amount + prior_december.amount - prior_same_month.amount

    @classmethod
    def _monthly_balances(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        *,
        cutoff_date: date,
    ) -> dict[str, tuple[Decimal, ...]]:
        values: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for line in lines:
            if (
                line.statement_type is FinancialStatementType.BALANCE_SHEET
                and line.statement_date <= cutoff_date
                and cls._code(line) in {cls._ASSETS, cls._EQUITY}
            ):
                values[cls._code(line)][line.statement_date] = line.amount
        return {
            code: tuple(amount for _, amount in sorted(dated.items(), reverse=True)[:12])
            for code, dated in values.items()
        }

    @classmethod
    def _average(cls, values: tuple[Decimal, ...]) -> Decimal | None:
        if len(values) != cls._AVERAGE_MONTHS:
            return None
        return sum(values, start=Decimal("0")) / Decimal(cls._AVERAGE_MONTHS)

    @staticmethod
    def _ratio(numerator: Decimal, denominator: Decimal | None) -> Decimal | None:
        if denominator in {None, Decimal("0")}:
            return None
        try:
            return numerator / denominator
        except (DivisionByZero, InvalidOperation):
            return None

    @staticmethod
    def _code(line: FinancialStatementLine) -> str:
        return line.account_code.removesuffix(".0")

    @staticmethod
    def _line(
        *,
        entity: FinancialEntity,
        cutoff_date: date,
        code: str,
        label: str,
        value: Decimal,
        source: FinancialStatementLine,
        formula: str,
    ) -> FinancialStatementLine:
        source_url = source.trace.source_url if source.trace is not None else ""
        return FinancialStatementLine(
            entity=entity,
            statement_date=cutoff_date,
            statement_type=FinancialStatementType.INDICATORS,
            account_code=f"CALC:{code}",
            account_name=label,
            amount=value,
            currency="RATIO",
            trace=SourceTrace(
                source_name="Cálculo 08ME14-01 sobre API pública SUGEF",
                source_url=source_url,
                file_path=formula,
                sheet_name="08ME14-01 V01",
                row_number=0,
            ),
        )
