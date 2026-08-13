from __future__ import annotations

import csv
import os
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import openpyxl

from aip.tools.reconcile_portfolio_tir import main


def test_reconcile_portfolio_tir_cli_writes_csv_and_reports_tir_summary(tmp_path: Path, monkeypatch) -> None:
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
    worksheet.append([
        "Emisor",
        "ISIN",
        "Serie",
        "Código Producto",
        "Clasificación",
        "Reserva Liquidez",
        "Moneda",
        "Valor Mercado Colonizado",
        "Saldo Principal",
        "Saldo Valor Transado",
        "Saldo Valor Compra",
        "Saldo Valor Mercado",
        "Porcentaje Valor Compra",
        "Valuacion Acumulada",
        "Amortizacion Acumulada",
        "Interes Por Cobrar",
        "Cantidad Participaciones",
        "Monto Estimacion",
        "Monto Deterioro",
        "TIR",
        "Tasa Nominal",
        "Duracion",
        "DV01",
        "HHI",
        "Fecha Vencimiento",
    ])
    worksheet.append(["Banco Central", "CR1234567890", "S240327", "TPTBA", "V.C", "S", "CRC", 1000000.0, 1000000.0, 1000000.0, 1000000.0, 980000.0, 95.0, 100000.0, 20000.0, 5000.0, 3000.0, 50.0, 1000.0, 5.2, 4.3, 3.5, 10000.0, 2500.0, "2027-03-24"])
    worksheet.append(["Banco Central", "CR1234567891", "B180429", "TPTBA", "costo amortizado", "S", "USD", 250000.0, 250000.0, 250000.0, 250000.0, 250000.0, 100.0, 120000.0, 30000.0, 6000.0, 4000.0, 1500.0, 400.0, None, 6.1, 4.2, 12000.0, 3100.0, "2029-04-18"])
    worksheet.append(["Banco Central", "CR1234567892", "S240328", "TPTBA", "V.C", "S", "CRC", 500000.0, 500000.0, 500000.0, 500000.0, 480000.0, 95.0, 100000.0, 20000.0, 5000.0, 3000.0, 50.0, 1000.0, None, None, 3.5, 10000.0, 2500.0, "2027-03-24"])
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

    output_path = tmp_path / "portfolio_tir.csv"
    buffer = StringIO()
    with redirect_stdout(buffer):
        exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 3
    assert rows[0]["rate_source"] == "MASTER_TIR"
    assert rows[1]["rate_source"] == "FACIAL_RATE_FALLBACK"
    assert rows[2]["rate_source"] == "MISSING_RATE_REVIEW"
    assert rows[0]["effective_rate"] == "5.20"
    assert rows[1]["effective_rate"] == "6.10"
    assert rows[2]["effective_rate"] == ""
    assert rows[0]["market_value_crc"]
    assert rows[1]["market_value_crc"]
    assert rows[2]["market_value_crc"]

    report = buffer.getvalue()
    assert "TIR RECONCILIATION REPORT" in report
    assert "MASTER TIR SOURCE" in report
    assert "FACIAL RATE FALLBACK" in report
    assert "MISSING RATE REVIEW" in report
    assert "EXCLUDED" in report
    assert "COMBINED PORTFOLIO TIR" in report

    completed = subprocess.run(
        [sys.executable, "-m", "aip.tools.reconcile_portfolio_tir", "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
        env={**dict(os.environ), "PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")},
    )
    assert completed.returncode == 0
    assert "TIR RECONCILIATION REPORT" in completed.stdout
