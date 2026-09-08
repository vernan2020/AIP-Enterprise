from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Literal

from aip.domain.financial_analysis.models import FinancialStatementLine, FinancialStatementType

ROAStatus = Literal["CALCULATED", "INSUFFICIENT_HISTORY", "DATA_UNAVAILABLE"]


@dataclass(frozen=True, slots=True)
class ReturnOnAssetsResult:
    """Auditable institutional ROA calculation result."""

    value_percent: Decimal | None
    annualized_net_income: Decimal | None
    average_assets_12m: Decimal | None
    asset_observations: int
    status: ROAStatus
    source_account: str


class ReturnOnAssetsService:
    """Calculate ROA from annualized final income and 12-month average assets.

    Institutional methodology:
        ROA = annualized final income / average total assets of the last 12 months.

    Income statement figures are treated as year-to-date cumulative amounts. The
    annualization factor is therefore 12 / cutoff_month. The asset denominator
    requires one valid month-end total-assets balance for each of the 12 calendar
    months ending at the requested cutoff; missing months are never imputed.
    """

    LOOKBACK_MONTHS = 12
    SOURCE_ACCOUNT = (
        "DERIVADO SUGEF: utilidad final anualizada / promedio últimos 12 meses "
        "de activos totales"
    )
    _ASSET_TERMS = ("TOTAL ACTIVO", "ACTIVO TOTAL")
    _NET_INCOME_TERMS = (
        "RESULTADO DEL PERIODO",
        "RESULTADO NETO",
        "UTILIDAD NETA",
        "EXCEDENTE NETO",
        "RESULTADO FINAL",
    )

    @classmethod
    def calculate(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        *,
        entity_id: str,
        cutoff_date: date,
    ) -> ReturnOnAssetsResult:
        current = tuple(
            line
            for line in lines
            if line.entity.entity_id == entity_id and line.statement_date == cutoff_date
        )
        net_income = cls._find_value(
            current,
            cls._NET_INCOME_TERMS,
            statement_type=FinancialStatementType.INCOME_STATEMENT,
        )
        if net_income is None:
            return cls._unavailable("DATA_UNAVAILABLE", 0)

        expected_months = cls._expected_months(cutoff_date, cls.LOOKBACK_MONTHS)
        assets: list[Decimal] = []
        for year, month in expected_months:
            month_lines = tuple(
                line
                for line in lines
                if line.entity.entity_id == entity_id
                and line.statement_type is FinancialStatementType.BALANCE_SHEET
                and line.statement_date <= cutoff_date
                and line.statement_date.year == year
                and line.statement_date.month == month
            )
            value = cls._find_value(
                month_lines,
                cls._ASSET_TERMS,
                statement_type=FinancialStatementType.BALANCE_SHEET,
            )
            if value is not None:
                assets.append(value)

        if len(assets) != cls.LOOKBACK_MONTHS:
            return cls._unavailable("INSUFFICIENT_HISTORY", len(assets))

        average_assets = sum(assets, Decimal("0")) / Decimal(cls.LOOKBACK_MONTHS)
        if average_assets == 0:
            return cls._unavailable("DATA_UNAVAILABLE", len(assets))

        annualized_income = net_income * Decimal("12") / Decimal(cutoff_date.month)
        try:
            roa = annualized_income / average_assets * Decimal("100")
        except (DivisionByZero, InvalidOperation):
            return cls._unavailable("DATA_UNAVAILABLE", len(assets))

        return ReturnOnAssetsResult(
            value_percent=roa,
            annualized_net_income=annualized_income,
            average_assets_12m=average_assets,
            asset_observations=len(assets),
            status="CALCULATED",
            source_account=cls.SOURCE_ACCOUNT,
        )

    @classmethod
    def _unavailable(cls, status: ROAStatus, observations: int) -> ReturnOnAssetsResult:
        return ReturnOnAssetsResult(
            value_percent=None,
            annualized_net_income=None,
            average_assets_12m=None,
            asset_observations=observations,
            status=status,
            source_account=cls.SOURCE_ACCOUNT,
        )

    @classmethod
    def _find_value(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        terms: tuple[str, ...],
        *,
        statement_type: FinancialStatementType,
    ) -> Decimal | None:
        candidates: list[tuple[int, int, int, date, FinancialStatementLine]] = []
        for line in lines:
            if line.statement_type is not statement_type:
                continue
            normalized = cls._normalize(line.account_name)
            for term in terms:
                if normalized == term:
                    candidates.append(
                        (cls._source_priority(line), 0, len(normalized), line.statement_date, line)
                    )
                elif term in normalized:
                    candidates.append(
                        (cls._source_priority(line), 1, len(normalized), line.statement_date, line)
                    )
        if not candidates:
            return None
        selected = min(
            candidates,
            key=lambda item: (item[0], item[1], item[2], -item[3].toordinal()),
        )[4]
        return selected.amount

    @classmethod
    def _expected_months(cls, cutoff_date: date, months: int) -> tuple[tuple[int, int], ...]:
        month_index = cutoff_date.year * 12 + cutoff_date.month - 1
        values: list[tuple[int, int]] = []
        for offset in reversed(range(months)):
            year, zero_based_month = divmod(month_index - offset, 12)
            values.append((year, zero_based_month + 1))
        return tuple(values)

    @classmethod
    def _source_priority(cls, line: FinancialStatementLine) -> int:
        source = cls._normalize(line.trace.source_name if line.trace is not None else "")
        if "API PUBLICA" in source or ("SUGEF" in source and "CALCULO" not in source):
            return 0
        if "CALCULO 08ME14-01" in source:
            return 1
        return 2

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )
