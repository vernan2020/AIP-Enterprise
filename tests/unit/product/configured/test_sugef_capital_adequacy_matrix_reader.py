from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_capital_adequacy_matrix_reader import (
    SUGEFCapitalAdequacyMatrixReader,
)
from aip.product.configured.readers.sugef_capital_adequacy_reader import (
    SUGEFCapitalAdequacyReader,
)
from aip.product.configured.readers.sugef_public_api_client import (
    SUGEFPublicApiResponse,
)


class _EntityApi:
    def list_entities(self) -> SUGEFPublicApiResponse:
        rows = (
            {
                "codigoEntidad": "3004045138",
                "nombreEntidad": "Cooperativa de Ahorro y Crédito Alianza de Pérez Zeledón R.L.",
                "aliasEntidad": "COOPEALIANZA",
                "aliasPublicacionEntidad": "COOPEALIANZA",
                "descripcionSector": "Cooperativas",
            },
            {
                "codigoEntidad": "1001001001",
                "nombreEntidad": "Banco de Costa Rica",
                "aliasEntidad": "BANCO DE COSTA RICA",
                "aliasPublicacionEntidad": "BANCO DE COSTA RICA",
                "descripcionSector": "Bancos estatales",
            },
            {
                "codigoEntidad": "1001001002",
                "nombreEntidad": "Banco Nacional",
                "aliasEntidad": "BANCO NACIONAL",
                "aliasPublicacionEntidad": "BANCO NACIONAL",
                "descripcionSector": "Bancos estatales",
            },
        )
        return SUGEFPublicApiResponse(
            operation="/Catalogo/MAPI/ListarEntidades",
            endpoint="https://sugef.example/entities",
            method="GET",
            body={"listaEntidades": list(rows)},
            rows=rows,
        )


def _official_horizontal_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Histórico"
    sheet.append(
        (
            "Entidad",
            date(2025, 12, 1),
            date(2026, 3, 1),
            date(2026, 6, 1),
        )
    )
    sheet.append(("BANCO DE COSTA RICA", 0.1420, 0.1353, 0.1337))
    sheet.append(("BANCO NACIONAL", 0.1491, 0.1465, 0.1511))
    sheet.append(("COOPEALIANZA", 0.2000, 0.2008, 0.1952))
    payload = io.BytesIO()
    workbook.save(payload)
    return payload.getvalue()


def _page() -> bytes:
    return b"""
    <html><body>
      <a href="/reportes/suficiencia/Suficiencia%20Patrimonial%20(Junio%202026).xlsx">
        Junio 2026
      </a>
    </body></html>
    """


def test_reader_supports_official_horizontal_history_matrix() -> None:
    workbook = _official_horizontal_workbook()

    def fetch(url: str) -> bytes:
        if url == SUGEFCapitalAdequacyReader.SOURCE_PAGE:
            return _page()
        return workbook

    reader = SUGEFCapitalAdequacyMatrixReader(
        SUGEFFinancialSourceConfig(),
        api_client=_EntityApi(),  # type: ignore[arg-type]
        fetch_bytes=fetch,
    )

    result = reader.read(date(2026, 7, 31))

    assert result.source_cutoff == date(2026, 6, 30)
    assert len(result.lines) == 3
    coopealianza = next(
        line for line in result.lines if line.entity.entity_id == "3004045138"
    )
    assert coopealianza.amount == Decimal("0.1952")
    assert coopealianza.statement_date == date(2026, 7, 31)
    assert coopealianza.trace is not None
    assert coopealianza.trace.sheet_name == "Histórico"
    assert coopealianza.trace.row_number == 4
    assert "30/06/2026" in coopealianza.trace.file_path
    assert any(
        "matriz histórica horizontal por corte" in diagnostic
        for diagnostic in result.diagnostics
    )


def test_reader_does_not_take_previous_quarter_from_horizontal_matrix() -> None:
    workbook = _official_horizontal_workbook()

    def fetch(url: str) -> bytes:
        if url == SUGEFCapitalAdequacyReader.SOURCE_PAGE:
            return _page()
        return workbook

    reader = SUGEFCapitalAdequacyMatrixReader(
        SUGEFFinancialSourceConfig(),
        api_client=_EntityApi(),  # type: ignore[arg-type]
        fetch_bytes=fetch,
    )

    result = reader.read(date(2026, 7, 31))

    coopealianza = next(
        line for line in result.lines if line.entity.entity_id == "3004045138"
    )
    assert coopealianza.amount != Decimal("0.2008")
    assert coopealianza.amount == Decimal("0.1952")
