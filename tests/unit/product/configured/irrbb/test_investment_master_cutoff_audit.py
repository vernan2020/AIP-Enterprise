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
    assert len(result["maturity_bands"]) == 38
    bands = {(row["source_currency"], row["ordinal"]): row for row in result["maturity_bands"]}
    assert bands[("CRC", 4)]["source_principal"] == "125.75"
    assert bands[("USD", 4)]["source_principal"] == "72.25"
    assert bands[("CRC", 4)]["positions"] == 1
    assert bands[("CRC", 1)]["source_principal"] == "0"
    assert bands[("USD", 19)]["positions"] == 0
    exclusions = result["maturity_exclusions"]
    assert exclusions == [
        {
            "source_currency": "(SIN MONEDA NATIVA)",
            "reason": "MISSING_NATIVE_CURRENCY",
            "positions": 1,
            "valid_source_principal": "500",
        }
    ]
    recon = {item["source_currency"]: item for item in result["maturity_reconciliation"]}
    assert recon["CRC"]["observed_principal"] == "125.75"
    assert recon["CRC"]["difference"] == "0"
    assert recon["USD"]["excluded_valid_principal"] == "0"
    assert recon["(SIN MONEDA NATIVA)"]["eligible_source_principal"] == "500"
    assert recon["(SIN MONEDA NATIVA)"]["excluded_valid_principal"] == "500"
    assert recon["(SIN MONEDA NATIVA)"]["status"] == "BLOCKED_NATIVE_CURRENCY"


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


def test_investment_maturity_invalid_date_excludes_valid_principal(tmp_path):
    folder = _root(tmp_path)
    filename = tmp_path / "Inversiones" / "2026" / "maestro" / "09" / "30-09-2026.xlsx"
    from openpyxl import load_workbook

    workbook = load_workbook(filename)
    sheet = workbook.active
    sheet.cell(row=2, column=5).value = date(2026, 9, 1)
    workbook.save(filename)
    report = inspect_investment_master_cutoff(cutoff=date(2026, 9, 30), folder=folder)
    crc_bands = [row for row in report["maturity_bands"] if row["source_currency"] == "CRC"]
    assert len(crc_bands) == 19
    assert all(row["source_principal"] == "0" for row in crc_bands)
    assert all(row["positions"] == 0 for row in crc_bands)
    excluded = [row for row in report["maturity_exclusions"] if row["source_currency"] == "CRC"]
    assert len(excluded) == 1
    assert excluded[0]["reason"] == "MISSING_OR_PAST_MATURITY"
    assert excluded[0]["valid_source_principal"] == "125.75"
    recon = [row for row in report["maturity_reconciliation"] if row["source_currency"] == "CRC"]
    assert recon[0]["eligible_source_principal"] == "125.75"
    assert recon[0]["observed_principal"] == "0"
    assert recon[0]["excluded_valid_principal"] == "125.75"


def test_unrecognized_source_currency_preserves_excluded_numeric_principal(tmp_path):
    folder = _root(tmp_path)
    filename = tmp_path / "Inversiones" / "2026" / "maestro" / "09" / "30-09-2026.xlsx"
    from openpyxl import load_workbook

    workbook = load_workbook(filename)
    sheet = workbook.active
    sheet.cell(row=3, column=4).value = "EUR"
    workbook.save(filename)

    result = inspect_investment_master_cutoff(cutoff=date(2026, 9, 30), folder=folder)
    assert result["status"] == "INVESTMENT_MASTER_SOURCE_INSPECTED_NOT_CERTIFIED"
    assert result["certified"] is False
    reconciliation = {
        entry["source_currency"]: entry for entry in result["maturity_reconciliation"]
    }
    assert reconciliation["EUR"]["eligible_source_principal"] == "500"
    assert reconciliation["EUR"]["excluded_valid_principal"] == "500"
    assert reconciliation["EUR"]["observed_principal"] == "0"
    assert reconciliation["EUR"]["status"] == "BLOCKED_NATIVE_CURRENCY"
    assert all(item["source_currency"] != "EUR" for item in result["maturity_bands"])
    assert any(
        item["source_currency"] == "EUR"
        and item["reason"] == "UNSUPPORTED_CURRENCY"
        and item["valid_source_principal"] == "500"
        for item in result["maturity_exclusions"]
    )
