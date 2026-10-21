"""Guard SUGEF source provenance and August-2026 peer membership."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.matrix_sugef_adapter import (
    REFERENCE_AUGUST_2026_CODES,
    MatrixSUGEFAdapter,
)
from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)


def _line(entity_id: str, name: str, indicator: str, value: str):
    return FinancialStatementLine(
        entity=FinancialEntity(entity_id, name),
        statement_date=date(2026, 8, 31),
        statement_type=FinancialStatementType.INDICATORS,
        account_code=indicator,
        account_name=indicator,
        amount=Decimal(value),
    )


def test_explicit_august_matrix_universe_has_38_unique_entities() -> None:
    assert len(REFERENCE_AUGUST_2026_CODES) == 38
    assert len(set(REFERENCE_AUGUST_2026_CODES)) == 38


def test_matched_cohort_uses_real_entity_ids_not_spreadsheet_aliases() -> None:
    rows = (
        _line("3000000001", "COOPENAE - Cooperativa Nacional de Educadores", "ROE", "0.06"),
        _line("3000000002", "BANCO LAFISE - Banco Lafise S.A.", "ROE", "-0.01"),
        _line("unmatched", "ENTIDAD FUERA DEL UNIVERSO", "ROE", "0.04"),
    )
    ids, missing = MatrixSUGEFAdapter.select_reference_entities(
        rows, date(2026, 8, 31)
    )
    assert ids == ("3000000001", "3000000002")
    assert len(missing) == 36
    assert "BANCO CMB" in missing


def test_extract_keeps_missing_real_ratios_missing() -> None:
    rows = (
        _line("id1", "COOPENAE - Cooperativa Nacional de Educadores", "ROE", "0.06"),
        _line("id1", "COOPENAE - Cooperativa Nacional de Educadores", "Aplica Supervisión Proporcional", "0"),
        _line("id1", "COOPENAE - Cooperativa Nacional de Educadores", "Garantía del Estado", "0"),
    )
    extraction = MatrixSUGEFAdapter.extract(
        rows, cutoff_date=date(2026, 8, 31), cohort_ids=("id1",)
    )
    item = extraction[0]
    assert item.indicators["ROE"] == Decimal("0.06")
    assert item.indicators["ROA"] is None
    assert item.indicators["LIQUIDITY_COVERAGE"] is None
    assert item.regulation_full is True
    assert item.state_guarantee is False
