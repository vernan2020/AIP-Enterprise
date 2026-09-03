from __future__ import annotations

from decimal import Decimal

import openpyxl

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialStatementReader,
)


def test_reader_normalizes_xlsx_and_preserves_source_trace(tmp_path) -> None:
    path = tmp_path / "EstadoResultados_SUGEF_202607.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Estado de Resultados"
    sheet.append(["Reporte oficial SUGEF"])
    sheet.append(
        [
            "Código entidad",
            "Entidad",
            "Tipo entidad",
            "Fecha de corte",
            "Código cuenta",
            "Descripción",
            "Saldo",
            "Moneda",
        ]
    )
    sheet.append(
        ["007", "Coopealianza R.L.", "Cooperativas", "31/07/2026", "500", "Resultado neto", 8_341_000_000, "CRC"]
    )
    workbook.save(path)

    reader = SUGEFFinancialStatementReader(
        SUGEFFinancialSourceConfig(enabled=True, root=str(tmp_path))
    )
    result = reader.read()

    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.entity.entity_id == "007"
    assert line.amount == Decimal("8341000000")
    assert line.statement_type == FinancialStatementType.INCOME_STATEMENT
    assert line.trace is not None
    assert line.trace.row_number == 3
    assert str(path) in result.source_files


def test_reader_reports_unconfigured_source_without_fabricating_data() -> None:
    result = SUGEFFinancialStatementReader(SUGEFFinancialSourceConfig()).read()

    assert result.lines == ()
    assert any("desactivada" in message for message in result.diagnostics)
    assert any("pendiente de validación" in message for message in result.diagnostics)
