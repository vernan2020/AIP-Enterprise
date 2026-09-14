from __future__ import annotations

import json
from datetime import date
from io import StringIO
from pathlib import Path

from aip.product.configured.irrbb.investment_source_readiness_cli import run
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
    InstitutionalPortfolioMasterReadResult,
)


def _column_mapping() -> dict[str, str]:
    return {
        "source_row": "#",
        "contract_number": "Numero Contrato",
        "currency": "Moneda",
        "maturity_date": "Fecha Vencimiento",
        "product_code": "Codigo Producto",
        "classification": "Clasificacion",
        "series": "Serie",
        "isin": "ISIN",
        "traded_balance": "Saldo Valor Transado",
        "principal_balance": "Saldo Principal",
        "book_value": "Saldo Valor Compra",
        "nominal_rate": "Tasa Nominal",
        "periodicity": "Periodicidad",
        "last_interest_payment_date": "Fecha Ultimo Pago Intereses",
        "variable_rate_flag": "Indicador Tasa Variable",
    }


def _position(*, variable_rate_flag: str = "N") -> dict[str, object]:
    return {
        "source_row": 7,
        "source_file": "maestro_2026-07-31.xlsx",
        "contract_number": "C-SECRET-100",
        "currency": "CRC",
        "maturity_date": date(2028, 7, 31),
        "product_code": "TP",
        "classification": "FVOCI",
        "series": "SER-SECRET-100",
        "isin": "CRSECRET000100",
        "traded_balance": 1_000_000.0,
        "principal_balance": 1_000_000.0,
        "book_value": 995_000.0,
        "nominal_rate": 6.25,
        "periodicity": "semestral",
        "last_interest_payment_date": date(2026, 7, 31),
        "variable_rate_flag": variable_rate_flag,
    }


def _result(
    source_file: str,
    *,
    variable_rate_flag: str = "N",
    source_status: str = "HEALTHY",
) -> InstitutionalPortfolioMasterReadResult:
    return InstitutionalPortfolioMasterReadResult(
        source_file=source_file,
        valuation_date=date(2026, 7, 31),
        sheet_selected="Maestro",
        normalized_positions=[_position(variable_rate_flag=variable_rate_flag)],
        warnings=(),
        rejected_row_count=0,
        source_status=source_status,
        detected_column_mapping=_column_mapping(),
    )


class _StubReader(InstitutionalPortfolioMasterReader):
    def __init__(self, result: InstitutionalPortfolioMasterReadResult) -> None:
        self.result = result
        self.calls: list[tuple[str | Path, date | None, bool]] = []

    def read(
        self,
        path: str | Path,
        *,
        valuation_date_override: date | None = None,
        diagnostic_mode: bool = False,
    ) -> InstitutionalPortfolioMasterReadResult:
        self.calls.append((path, valuation_date_override, diagnostic_mode))
        return self.result


class _FailingReader(InstitutionalPortfolioMasterReader):
    def read(
        self,
        path: str | Path,
        *,
        valuation_date_override: date | None = None,
        diagnostic_mode: bool = False,
    ) -> InstitutionalPortfolioMasterReadResult:
        raise OSError(f"cannot access {path}")


def test_cli_reports_readiness_without_emitting_contractual_rows_or_full_path(
    tmp_path: Path,
) -> None:
    private_path = tmp_path / "private" / "maestro_2026-07-31.xlsx"
    reader = _StubReader(_result(str(private_path)))
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--path", str(private_path)],
        stdout=stdout,
        stderr=stderr,
        reader=reader,
    )

    assert status == 0
    assert stderr.getvalue() == ""
    assert reader.calls == [(str(private_path), None, False)]

    report = json.loads(stdout.getvalue())
    assert report["report_type"] == "IRRBB_INVESTMENT_SOURCE_READINESS"
    assert report["source_file_name"] == private_path.name
    assert report["reader_valuation_date"] == "2026-07-31"
    assert report["source_status"] == "HEALTHY"
    assert report["accepted_position_count"] == 1
    assert report["rejected_row_count"] == 0
    assert report["warning_count"] == 0
    assert report["certification_status"] == "INCOMPLETE"
    assert report["production_activation_authorized"] is False
    assert "INV-CUTOFF-DATE" in report["not_assessed_requirement_ids"]

    rendered = stdout.getvalue()
    assert str(tmp_path) not in rendered
    assert "C-SECRET-100" not in rendered
    assert "SER-SECRET-100" not in rendered
    assert "CRSECRET000100" not in rendered
    assert "1000000" not in rendered
    assert "995000" not in rendered


def test_require_ready_returns_three_for_incomplete_source(tmp_path: Path) -> None:
    private_path = tmp_path / "maestro.xlsx"
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--path", str(private_path), "--require-ready"],
        stdout=stdout,
        stderr=stderr,
        reader=_StubReader(_result(str(private_path))),
    )

    assert status == 3
    assert json.loads(stdout.getvalue())["certification_status"] == "INCOMPLETE"
    assert stderr.getvalue() == ""


def test_floating_source_preserves_repricing_blockers(tmp_path: Path) -> None:
    private_path = tmp_path / "maestro.xlsx"
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--path", str(private_path), "--require-ready"],
        stdout=stdout,
        stderr=stderr,
        reader=_StubReader(_result(str(private_path), variable_rate_flag="S")),
    )

    assert status == 3
    report = json.loads(stdout.getvalue())
    assert report["certification_status"] == "BLOCKED"
    assert "INV-NEXT-REPRICING-DATE" in report["blocking_requirement_ids"]
    assert "INV-REPRICING-FREQUENCY" in report["blocking_requirement_ids"]
    assert report["production_activation_authorized"] is False
    assert stderr.getvalue() == ""


def test_source_access_failure_is_sanitized(tmp_path: Path) -> None:
    private_path = tmp_path / "private" / "maestro.xlsx"
    stdout = StringIO()
    stderr = StringIO()

    status = run(
        ["--path", str(private_path)],
        stdout=stdout,
        stderr=stderr,
        reader=_FailingReader(),
    )

    assert status == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "IRRBB investment readiness failed: source assessment error\n"
    assert str(tmp_path) not in stderr.getvalue()


def test_missing_path_is_a_usage_error() -> None:
    stdout = StringIO()
    stderr = StringIO()

    status = run([], stdout=stdout, stderr=stderr)

    assert status == 2
    assert stdout.getvalue() == ""
    assert "--path" in stderr.getvalue()
