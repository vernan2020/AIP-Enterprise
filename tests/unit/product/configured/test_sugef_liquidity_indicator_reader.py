from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_liquidity_indicator_reader import (
    SUGEFLiquidityIndicatorReader,
)
from aip.product.configured.readers.sugef_trial_balance_reader import (
    SUGEFTrialBalanceLine,
    SUGEFTrialBalanceReadResult,
)


def _line(
    cutoff_date: date,
    *,
    entity_code: str,
    entity_name: str,
    account_code: str,
    amount: Decimal | None,
    row: int,
) -> SUGEFTrialBalanceLine:
    return SUGEFTrialBalanceLine(
        sector_code="7",
        sector_name="Bancos",
        entity_code=entity_code,
        entity_name=entity_name,
        statement_date=cutoff_date,
        account_code=account_code,
        catalog_type_code="14",
        account_name=account_code,
        account_level=Decimal("1"),
        ending_balance=amount,
        endpoint="https://sugef.example/balanza",
        source_row=row,
    )


class _TrialReader:
    def read(
        self,
        cutoff_date: date,
        *,
        entity_codes: tuple[str, ...] | None = None,
        include_all_entities: bool = True,
        account_code: str = "",
    ) -> SUGEFTrialBalanceReadResult:
        del entity_codes, include_all_entities, account_code
        rows = [
            _line(
                cutoff_date,
                entity_code="3004045138",
                entity_name="COOPEALIANZA R.L.",
                account_code=code,
                amount=Decimal(amount),
                row=index,
            )
            for index, (code, amount) in enumerate(
                (
                    ("11000000", "100"),
                    ("12000000", "200"),
                    ("12500000", "50"),
                    ("21000000", "700"),
                ),
                start=1,
            )
        ]
        return SUGEFTrialBalanceReadResult(
            tuple(rows),
            ("https://sugef.example/balanza",),
            (),
        )


class _RecoveryTrialReader:
    def __init__(self, *, null_available_investments: bool = False) -> None:
        self.null_available_investments = null_available_investments
        self.calls: list[tuple[tuple[str, ...] | None, bool]] = []

    def read(
        self,
        cutoff_date: date,
        *,
        entity_codes: tuple[str, ...] | None = None,
        include_all_entities: bool = True,
        account_code: str = "",
    ) -> SUGEFTrialBalanceReadResult:
        del account_code
        self.calls.append((entity_codes, include_all_entities))
        entity_code = "BAC"
        entity_name = "BANCO BAC SAN JOSE"
        rows = [
            _line(
                cutoff_date,
                entity_code=entity_code,
                entity_name=entity_name,
                account_code="11000000",
                amount=Decimal("100"),
                row=1,
            ),
            _line(
                cutoff_date,
                entity_code=entity_code,
                entity_name=entity_name,
                account_code="12000000",
                amount=Decimal("200"),
                row=2,
            ),
            _line(
                cutoff_date,
                entity_code=entity_code,
                entity_name=entity_name,
                account_code="21000000",
                amount=Decimal("700"),
                row=3,
            ),
        ]
        if entity_codes is not None and self.null_available_investments:
            rows.append(
                _line(
                    cutoff_date,
                    entity_code=entity_code,
                    entity_name=entity_name,
                    account_code="12500000",
                    amount=None,
                    row=4,
                )
            )
        return SUGEFTrialBalanceReadResult(
            tuple(rows),
            ("https://sugef.example/balanza",),
            (),
        )


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


def test_liquidity_reader_confirms_unreported_numerator_as_zero_by_direct_query() -> None:
    trial_reader = _RecoveryTrialReader()
    reader = SUGEFLiquidityIndicatorReader(
        SUGEFFinancialSourceConfig(),
        trial_balance_reader=trial_reader,  # type: ignore[arg-type]
    )

    result = reader.read(
        date(2026, 7, 31),
        expected_entity_codes=("BAC",),
    )

    assert len(result.lines) == 1
    assert result.lines[0].amount == Decimal("300") / Decimal("700")
    assert (("BAC",), False) in trial_reader.calls
    assert any("12500000" in item and "saldo reportado" in item for item in result.diagnostics)


def test_liquidity_reader_never_converts_reported_null_balance_to_zero() -> None:
    trial_reader = _RecoveryTrialReader(null_available_investments=True)
    reader = SUGEFLiquidityIndicatorReader(
        SUGEFFinancialSourceConfig(),
        trial_balance_reader=trial_reader,  # type: ignore[arg-type]
    )

    result = reader.read(
        date(2026, 7, 31),
        expected_entity_codes=("BAC",),
    )

    assert result.lines == ()
    assert any("saldo nulo" in item for item in result.diagnostics)
