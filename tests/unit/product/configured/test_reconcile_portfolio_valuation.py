from __future__ import annotations

import csv
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import openpyxl

from aip.tools.reconcile_portfolio_valuation import _print_difference_rows, main


def test_print_difference_rows_handles_tied_difference_values() -> None:
    rows = [
        {
            "issuer": "Issuer A",
            "series": "S1",
            "product_code": "P1",
            "source_values": {
                "valor mercado colonizado": Decimal("100"),
                "saldo valor mercado": Decimal("50"),
            },
        },
        {
            "issuer": "Issuer B",
            "series": "S2",
            "product_code": "P2",
            "source_values": {
                "valor mercado colonizado": Decimal("200"),
                "saldo valor mercado": Decimal("150"),
            },
        },
    ]

    output = StringIO()
    with redirect_stdout(output):
        _print_difference_rows(rows)

    report = output.getvalue()
    assert "TOP 30 POSITIONS CONTRIBUTING TO DIFFERENCE" in report
    assert "Issuer A" in report
    assert "Issuer B" in report


def test_print_difference_rows_handles_all_zero_differences() -> None:
    rows = [
        {
            "issuer": "Issuer A",
            "series": "S1",
            "product_code": "P1",
            "source_values": {
                "valor mercado colonizado": Decimal("100"),
                "saldo valor mercado": Decimal("100"),
            },
        },
        {
            "issuer": "Issuer B",
            "series": "S2",
            "product_code": "P2",
            "source_values": {
                "valor mercado colonizado": Decimal("200"),
                "saldo valor mercado": Decimal("200"),
            },
        },
    ]

    output = StringIO()
    with redirect_stdout(output):
        _print_difference_rows(rows)

    report = output.getvalue()
    assert "TOP 30 POSITIONS CONTRIBUTING TO DIFFERENCE" in report
    assert "difference=0.00" in report


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
        "Duracion",
        "DV01",
        "HHI",
        "Fecha Vencimiento",
    ])
    worksheet.append(["Banco Central", "CR1234567890", "S240327", "TPTBA", "V.C", "S", "CRC", 1000000.0, 1000000.0, 1000000.0, 1000000.0, 980000.0, 95.0, 100000.0, 20000.0, 5000.0, 3000.0, 50.0, 1000.0, 200.0, 5.2, 3.5, 10000.0, 2500.0, "2027-03-24"])
    worksheet.append(["Banco Central", "CR1234567891", "B180429", "TPTBA", "costo amortizado", "S", "USD", 250000.0, 250000.0, 250000.0, 250000.0, 250000.0, 100.0, 120000.0, 30000.0, 6000.0, 4000.0, 1500.0, 400.0, 4.8, 4.2, 12000.0, 3100.0, "2029-04-18"])
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
    assert "MONETARY FIELDS FROM MASTER" in completed.stdout
    assert "VALUE BRIDGE" in completed.stdout
    assert "TOP 30 USD POSITIONS" in completed.stdout
    assert "TOP 30 DIFFERENCES" in completed.stdout
