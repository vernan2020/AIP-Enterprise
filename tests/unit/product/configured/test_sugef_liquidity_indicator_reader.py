from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.configuration.configured_source_config import SUGEFFinancialSourceConfig
from aip.product.configured.readers.sugef_liquidity_indicator_reader import SUGEFLiquidityIndicatorReader
from aip.product.configured.readers.sugef_trial_balance_reader import (
    SUGEFTrialBalanceLine,
    SUGEFTrialBalanceReadResult,
)


class _TrialReader:
    def read(self, cutoff_date: date, *, include_all_entities: bool = True):
        rows = []
        for code, amount in (
            ("11000000", "100"),
            ("12000000", "200"),
            ("12500000", "50"),
            ("21000000", "700"),
        ):
            rows.append(
                SUGEFTrialBalanceLine(
                    sector_code="7",
                    sector_name="Cooperativas",
                    entity_code="3004045138",
                    entity_name="COOPEALIANZA R.L.",
                    statement_date=cutoff_date,
                    account_code=code,
                    catalog_type_code="14",
                    account_name=code,
                    account_level=Decimal("1"),
                    ending_balance=Decimal(amount),
                    endpoint="https://sugef.example/balanza",
                    source_row=len(rows) + 1,
                )
            )
        return SUGEFTrialBalanceReadResult(tuple(rows), ("https://sugef.example/balanza",), ())


def test_liquidity_reader_emits_calculated_indicator() -> None:
    reader = SUGEFLiquidityIndicatorReader(
        SUGEFFinancialSourceConfig(),
        trial_balance_reader=_TrialReader(),  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.account_code == "CALC:LIQUIDITY_COVERAGE"
    assert line.amount == Decimal("0.5")
    assert "11000000+12000000+12500000" in (line.trace.file_path if line.trace else "")
