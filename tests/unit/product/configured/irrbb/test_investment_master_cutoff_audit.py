from __future__ import annotations

from datetime import date

from openpyxl import Workbook

from aip.product.configured.configuration.configured_source_config import (
    FolderWatchSourceConfig,
)
from aip.product.configured.irrbb.investment_master_cutoff_audit import (
    inspect_investment_master_cutoff,
)


def _root(tmp_path, *, day="30-09-2026"):
    folder = tmp_path / "Inversiones" / "2026" / "maestro" / "09"
    folder.mkdir(parents=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Maestro"
    sheet.append(
        (
            "ISIN",
            "Emisor",
            "Numero Contrato",
            "Moneda",
            "Fecha Vencimiento",
            "Saldo Principal",
            "Saldo Valor Mercado",
            "Saldo Valor Compra",
            "Serie",
            "Tasa Nominal",
        )
    )
    sheet.append(
        ("CR00001", "Gobierno", "CON001", "CRC", date(2027, 1, 1), 125.75, 125.5, 126, "A", 0.05)
    )
    sheet.append(
        ("CR00002", "Gobierno", "CON002", None, date(2028, 1, 1), 500, 500, 500, "B", 0.05)
    )
    sheet.append(
        ("US00003", "Gobierno", "CON003", "USD", date(2027, 3, 1), 72.25, 72, 73, "C", 0.04)
    )
    workbook.save(folder / f"{day}.xlsx")
    return FolderWatchSourceConfig(
        enabled=True,
        portfolio_root=str(tmp_path),
        portfolio_master_pattern=r"Inversiones\{year}\maestro\{month}\*.xls*",
    )


def test_real_reader_audits_exact_cutoff_and_does_not_assume_crc_for_blank_currency(tmp_path):
    folder = _root(tmp_path)
    result = inspect_investment_master_cutoff(cutoff=date(2026, 9, 30), folder=folder)
    assert result["status"] == "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED"
    assert result["accepted_positions"] == 3
    assert result["certified"] is False
    assert result["filename_cutoff_only"] is True
    amounts = {item["source_currency"]: item for item in result["currencies"]}
    assert amounts["CRC"]["source_principal"] == "125.75"
    assert amounts["USD"]["source_principal"] == "72.25"
    assert amounts["(SIN MONEDA NATIVA)"]["principal_missing"] == 1
    assert amounts["(SIN MONEDA NATIVA)"]["source_principal"] == "0"
    assert "CON001" not in str(result)
    assert "CR00001" not in str(result)


def test_master_never_falls_back_to_prior_cutoff(tmp_path):
    folder = _root(tmp_path, day="29-09-2026")
    result = inspect_investment_master_cutoff(cutoff=date(2026, 9, 30), folder=folder)
    assert result["status"] == "EXACT_CUTOFF_MASTER_NOT_FOUND"
    assert result["certified"] is False


def test_master_blocks_ambiguous_same_day_files(tmp_path):
    folder = _root(tmp_path)
    master = tmp_path / "Inversiones" / "2026" / "maestro" / "09" / "30-09-2026.xlsx"
    master.with_suffix(".xls").write_bytes(b"not a trusted workbook")
    result = inspect_investment_master_cutoff(cutoff=date(2026, 9, 30), folder=folder)
    assert result["status"] == "AMBIGUOUS_MASTER_FILES"
    assert result["matching_master_count"] == 2
