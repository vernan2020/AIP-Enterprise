from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
import xlwt

from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)
from aip.product.configured.readers.pipca_vector_reader import InstitutionalPiPCAVectorReader


def _write_institutional_xls(path: Path) -> None:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Maestro")
    sheet.write(0, 0, "Resumen institucional")
    sheet.write(2, 0, "#")
    sheet.write(2, 1, "Emisor")
    sheet.write(2, 2, "Número Contrato")
    sheet.write(2, 3, "Puesto Bolsa")
    sheet.write(2, 4, "Moneda")
    sheet.write(2, 5, "Fecha Ingreso")
    sheet.write(2, 6, "Fecha Emision")
    sheet.write(2, 7, "Fecha Vencimiento")
    sheet.write(2, 8, "días al vencimiento")
    sheet.write(2, 9, "código producto")
    sheet.write(2, 10, "Clasificación")
    sheet.write(2, 11, "Calificación Riesgo")
    sheet.write(2, 12, "Reserva Liquidez")
    sheet.write(2, 13, "serie")
    sheet.write(2, 14, "Valor Mercado Colonizado")
    sheet.write(2, 15, "ISIN")
    sheet.write(2, 16, "saldo valor transado")
    sheet.write(2, 17, "Saldo Principal")
    sheet.write(2, 18, "porcentaje valor compra")
    sheet.write(2, 19, "saldo valor compra")
    sheet.write(2, 20, "porcentaje valor mercado")
    sheet.write(2, 21, "saldo valor mercado")
    sheet.write(2, 22, "tasa nominal")
    sheet.write(2, 23, "periodicidad")
    sheet.write(2, 24, "interes por cobrar")
    sheet.write(2, 25, "fecha ultimo pago intereses")
    sheet.write(2, 26, "Cantidad Participaciones")
    sheet.write(2, 27, "TIR")
    sheet.write(2, 28, "Indicador Tasa Variable")
    sheet.write(2, 29, "Indicador Público")
    sheet.write(2, 30, "Monto Estimación")
    sheet.write(2, 31, "Monto Deterioro")
    sheet.write(2, 32, "Custodio")

    sheet.write(3, 0, 1)
    sheet.write(3, 1, "Banco Central")
    sheet.write(3, 2, "CTR-001")
    sheet.write(3, 3, "Puesto A")
    sheet.write(3, 4, "CRC")
    sheet.write(3, 5, date(2023, 1, 15))
    sheet.write(3, 6, date(2022, 1, 15))
    sheet.write(3, 7, date(2030, 1, 15))
    sheet.write(3, 8, 1800)
    sheet.write(3, 9, "BONO")
    sheet.write(3, 10, "V.C")
    sheet.write(3, 11, "AA")
    sheet.write(3, 12, "S")
    sheet.write(3, 13, "SER-001")
    sheet.write(3, 14, 1000000)
    sheet.write(3, 15, "CR1234567890")
    sheet.write(3, 16, 1000000)
    sheet.write(3, 17, 1000000)
    sheet.write(3, 18, 98.5)
    sheet.write(3, 19, 1000000)
    sheet.write(3, 20, 100.0)
    sheet.write(3, 21, 980000)
    sheet.write(3, 22, 8.25)
    sheet.write(3, 23, "M")
    sheet.write(3, 24, -1500)
    sheet.write(3, 25, date(2025, 1, 15))
    sheet.write(3, 26, 250)
    sheet.write(3, 27, 7.2)
    sheet.write(3, 28, "S")
    sheet.write(3, 29, "P")
    sheet.write(3, 30, 1000)
    sheet.write(3, 31, 0)
    sheet.write(3, 32, "Custodio X")

    sheet.write(4, 0, 2)
    sheet.write(4, 1, "Banco Central")
    sheet.write(4, 2, "CTR-001")
    sheet.write(4, 3, "Puesto A")
    sheet.write(4, 4, "CRC")
    sheet.write(4, 5, date(2023, 1, 15))
    sheet.write(4, 6, date(2022, 1, 15))
    sheet.write(4, 7, date(1900, 1, 1))
    sheet.write(4, 8, 1800)
    sheet.write(4, 9, "BONO")
    sheet.write(4, 10, "V.C")
    sheet.write(4, 11, "AA")
    sheet.write(4, 12, "S")
    sheet.write(4, 13, "SER-002")
    sheet.write(4, 14, -250000)
    sheet.write(4, 15, "CR1234567891")
    sheet.write(4, 16, 1000000)
    sheet.write(4, 17, 1000000)
    sheet.write(4, 18, 98.5)
    sheet.write(4, 19, 1000000)
    sheet.write(4, 20, 100.0)
    sheet.write(4, 21, -980000)
    sheet.write(4, 22, 8.25)
    sheet.write(4, 23, "M")
    sheet.write(4, 24, -1500)
    sheet.write(4, 25, date(2025, 1, 15))
    sheet.write(4, 26, 250)
    sheet.write(4, 27, 7.2)
    sheet.write(4, 28, "S")
    sheet.write(4, 29, "P")
    sheet.write(4, 30, 1000)
    sheet.write(4, 31, 0)
    sheet.write(4, 32, "Custodio X")

    workbook.save(str(path))


def test_institutional_master_reader_parses_verified_headers_and_sentinels(tmp_path: Path) -> None:
    path = tmp_path / "maestro.xls"
    _write_institutional_xls(path)

    result = InstitutionalPortfolioMasterReader().read(path, valuation_date_override=date(2026, 7, 29))

    assert result.source_status == "HEALTHY"
    assert result.rejected_row_count == 0
    assert len(result.normalized_positions) == 2
    assert result.normalized_positions[0]["contract_number"] == "CTR-001"
    assert result.normalized_positions[0]["market_value"] == 980000.0
    assert result.normalized_positions[0]["book_value"] == 1000000.0
    assert result.normalized_positions[1]["maturity_date"] is None


def test_institutional_master_reader_emits_first_row_field_diagnostics_for_production_headers(tmp_path: Path) -> None:
    path = tmp_path / "maestro.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Maestro"
    worksheet.append(["  serie  ", "  código producto  ", " fecha vencimiento ", " ISIN ", "Valor de Mercado", "Valor en Libros"])
    worksheet.append(["ABC-001", "BONO", "2029-04-18", "CR123", 100, 90])
    workbook.save(path)

    result = InstitutionalPortfolioMasterReader().read(path, valuation_date_override=date(2026, 7, 29), diagnostic_mode=True)

    assert result.source_status == "HEALTHY"
    assert result.normalized_positions[0]["series"] == "ABC-001"
    assert result.normalized_positions[0]["product_code"] == "BONO"
    assert result.normalized_positions[0]["maturity_date"] == date(2029, 4, 18)
    assert result.normalized_positions[0]["isin"] == "CR123"
    assert result.diagnostics["column_mapping"]["series"].strip().lower() == "serie"
    assert result.diagnostics["column_mapping"]["product_code"].strip().lower() == "código producto"
    assert result.diagnostics["column_mapping"]["maturity_date"].strip().lower() == "fecha vencimiento"
    assert result.diagnostics["column_mapping"]["isin"].strip().lower() == "isin"

    first_row_debug = result.diagnostics["trace"]["first_accepted_row_field_diagnostics"][0]
    assert first_row_debug["fields"]["serie"]["excel_column_header"].strip().lower() == "serie"
    assert first_row_debug["fields"]["serie"]["raw_cell_value"] == "ABC-001"
    assert first_row_debug["fields"]["serie"]["normalized_value"] == "ABC-001"
    assert first_row_debug["fields"]["codigo producto"]["raw_cell_value"] == "BONO"
    assert first_row_debug["fields"]["codigo producto"]["normalized_value"] == "BONO"
    assert first_row_debug["fields"]["fecha vencimiento"]["raw_cell_value"] == "2029-04-18"
    assert first_row_debug["fields"]["fecha vencimiento"]["normalized_value"] == "2029-04-18"
    assert first_row_debug["fields"]["ISIN"]["raw_cell_value"] == "CR123"
    assert first_row_debug["fields"]["ISIN"]["normalized_value"] == "CR123"


def test_pipca_vector_reader_parses_positional_records_and_rejects_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "VectorPiPCA_20260729.txt"
    path.write_text(
        "BCCR bem  BC12M120826 12/08/2026  0.000 100.008344  2.842 0.000000 0\n"
        "BCR  bc13cBCRCRC13112613/11/2026  0.000 100.324641  3.714 0.000000 0\n"
        "bad line without enough fields\n",
        encoding="utf-8",
    )

    result = InstitutionalPiPCAVectorReader().read(path, source_cutoff=date(2026, 7, 29))

    assert result.accepted_count == 2
    assert result.rejected_count == 1
    assert result.records[0].issuer == "BCCR"
    assert result.records[0].series_or_security_code == "BC12M120826"
    assert result.records[0].maturity_date_if_present == date(2026, 8, 12)
    assert result.records[1].instrument_type_or_mnemonic == "bc13c"
