from __future__ import annotations

import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

import openpyxl

from aip.tools.reconcile_portfolio_valuation import main


def test_reconcile_portfolio_valuation_cli_writes_csv_and_reports_summaries(tmp_path: Path, monkeypatch) -> None:
    investments_root = tmp_path / "Inversiones"
    year_root = investments_root / "2026"
    maestro_root = year_root / "maestro" / "julio"
    maestro_root.mkdir(parents=True)

    vector_root = tmp_path / "vector" / "julio"
    vector_root.mkdir(parents=True)

    workbook_path = maestro_root / "29-07-2026.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Maestro"
    worksheet.append(["Emisor", "ISIN", "Serie", "Código Producto", "Clasificación", "Reserva Liquidez", "Moneda", "Valor Mercado Colonizado", "Saldo Principal", "Saldo Valor Compra", "Saldo Valor Mercado", "TIR", "Fecha Vencimiento"])
    worksheet.append(["Banco Central", "CR1234567890", "S240327", "TPTBA", "V.C", "S", "CRC", 1000000.0, 1000000.0, 1000000.0, 980000.0, 5.2, "2027-03-24"])
    worksheet.append(["Banco Central", "CR1234567891", "B180429", "TPTBA", "costo amortizado", "S", "CRC", 250000.0, 250000.0, 250000.0, 250000.0, 4.8, "2029-04-18"])
    workbook.save(workbook_path)

    vector_path = vector_root / "VectorPiPCA_20260729.txt"
    vector_path.write_text(
        "BCCR TPTBA S240327 24/03/2027 100.000 100.500 5.10 0.000000 0\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("AIP_EXECUTION_MODE", "CONFIGURED")
    monkeypatch.setenv("AIP_PORTFOLIO_ROOT", str(investments_root))
    monkeypatch.setenv("AIP_VECTOR_PATH", str(vector_root))
    monkeypatch.setenv("AIP_FOLDERWATCH_ENABLED", "true")
    monkeypatch.setenv("AIP_VECTOR_ENABLED", "true")
    monkeypatch.setenv("AIP_ALLOW_PRIOR_SOURCE_DATE", "true")
    monkeypatch.setenv("AIP_DATA_CUTOFF_DATE", "2026-07-29")
    monkeypatch.setenv("AIP_CONFIGURED_DIAGNOSTIC_MODE", "true")

    output_path = tmp_path / "portfolio_reconciliation.csv"
    exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    assert rows[0]["source_row"] == "2"
    assert rows[0]["issuer"] == "Banco Central"
    assert rows[0]["matched_status"] in {"MATCHED", "UNMATCHED"}
    assert rows[0]["reason"]
    assert rows[0]["aip_market_value"]

    completed = subprocess.run(
        [sys.executable, "-m", "aip.tools.reconcile_portfolio_valuation", "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")},
    )
    assert completed.returncode == 0
    assert "RECONCILIATION REPORT" in completed.stdout
    assert "AGGREGATE TOTALS" in completed.stdout
    assert "TOP 30 DIFFERENCES" in completed.stdout
