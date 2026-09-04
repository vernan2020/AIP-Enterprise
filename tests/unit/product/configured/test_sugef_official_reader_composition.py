from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_capital_adequacy_reader import (
    SUGEFCapitalAdequacyReadResult,
)
from aip.product.configured.readers.sugef_credit_quality_reader import (
    SUGEFCreditQualityReadResult,
)
from aip.product.configured.readers.sugef_financial_api_client import SUGEFApiReadResult
from aip.product.configured.readers.sugef_liquidity_indicator_reader import (
    SUGEFLiquidityIndicatorReadResult,
)
from aip.product.configured.readers.sugef_official_financial_statement_reader import (
    SUGEFOfficialFinancialStatementReader,
)

_ENTITY = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "Cooperativas")
_CUTOFF = date(2026, 7, 31)


def _line(statement_type: FinancialStatementType, code: str, name: str, amount: str):
    return FinancialStatementLine(
        entity=_ENTITY,
        statement_date=_CUTOFF,
        statement_type=statement_type,
        account_code=code,
        account_name=name,
        amount=Decimal(amount),
        currency="RATIO" if statement_type is FinancialStatementType.INDICATORS else "CRC",
    )


class _Api:
    def read(self, cutoff_date: date) -> SUGEFApiReadResult:
        assert cutoff_date == _CUTOFF
        return SUGEFApiReadResult(
            lines=(
                _line(FinancialStatementType.BALANCE_SHEET, "10000", "ACTIVO TOTAL", "1000"),
                _line(FinancialStatementType.INCOME_STATEMENT, "30000", "RESULTADO FINAL", "10"),
            ),
            endpoints=("https://sugef.example/base",),
            diagnostics=("base",),
        )


class _Credit:
    def read(self, cutoff_date: date) -> SUGEFCreditQualityReadResult:
        assert cutoff_date == _CUTOFF
        return SUGEFCreditQualityReadResult(
            lines=(
                _line(
                    FinancialStatementType.INDICATORS,
                    "CALC:CURRENT_PORTFOLIO",
                    "Cartera de crédito al día",
                    "0.95",
                ),
            ),
            endpoints=("https://sugef.example/credit",),
            diagnostics=("credit",),
        )


class _Liquidity:
    def read(
        self,
        cutoff_date: date,
        *,
        include_all_entities: bool = True,
    ) -> SUGEFLiquidityIndicatorReadResult:
        assert cutoff_date == _CUTOFF
        assert include_all_entities is True
        return SUGEFLiquidityIndicatorReadResult(
            lines=(
                _line(
                    FinancialStatementType.INDICATORS,
                    "CALC:LIQUIDITY_COVERAGE",
                    "Disponibilidades e Inversiones Disponibles / Obligaciones con el público",
                    "0.50",
                ),
            ),
            source_files=("https://sugef.example/balanza",),
            diagnostics=("liquidity",),
        )


class _Capital:
    def read(self, cutoff_date: date) -> SUGEFCapitalAdequacyReadResult:
        assert cutoff_date == _CUTOFF
        return SUGEFCapitalAdequacyReadResult(
            lines=(
                _line(
                    FinancialStatementType.INDICATORS,
                    "SUGEF:CAPITAL_ADEQUACY",
                    "Suficiencia Patrimonial",
                    "0.20",
                ),
            ),
            source_cutoff=date(2026, 6, 30),
            source_files=("https://sugef.example/sp.xlsx",),
            diagnostics=("capital",),
        )


def test_official_reader_composes_all_sugef_rating_sources() -> None:
    reader = SUGEFOfficialFinancialStatementReader(
        SUGEFFinancialSourceConfig(api_enabled=True, root=None),
        api_client=_Api(),  # type: ignore[arg-type]
        credit_quality_reader=_Credit(),  # type: ignore[arg-type]
        liquidity_reader=_Liquidity(),  # type: ignore[arg-type]
        capital_adequacy_reader=_Capital(),  # type: ignore[arg-type]
    )

    result = reader.read(cutoff_date=_CUTOFF)

    codes = {line.account_code for line in result.lines}
    assert {
        "10000",
        "30000",
        "CALC:CURRENT_PORTFOLIO",
        "CALC:LIQUIDITY_COVERAGE",
        "SUGEF:CAPITAL_ADEQUACY",
    } <= codes
    assert set(result.source_files) == {
        "https://sugef.example/base",
        "https://sugef.example/credit",
        "https://sugef.example/balanza",
        "https://sugef.example/sp.xlsx",
    }
    assert {"base", "credit", "liquidity", "capital"} <= set(result.diagnostics)
