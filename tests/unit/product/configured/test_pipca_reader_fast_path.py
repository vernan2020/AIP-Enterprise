from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.readers.pipca_vector_reader import (
    InstitutionalPiPCAVectorReader,
    InstitutionalVectorRecord,
)


def _sample_record() -> InstitutionalVectorRecord:
    return InstitutionalVectorRecord(
        issuer="BCCR",
        instrument_type_or_mnemonic="BONO",
        series_or_security_code="ABC",
        normalized_issuer_key="bccr",
        normalized_series_key="abc",
        isin_if_present="",
        maturity_date_if_present=None,
        coupon_or_reference_value=None,
        market_price=Decimal("100.50"),
        market_yield=None,
        spread_or_auxiliary_value=None,
        record_status="ACTIVE",
        source_cutoff=date(2026, 10, 2),
        source_line=1,
    )


def test_normal_vector_read_skips_expensive_line_diagnostics(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "VectorPiPCA_20261002.txt"
    path.write_text("sample vector row\n", encoding="utf-8")
    reader = InstitutionalPiPCAVectorReader()
    record = _sample_record()
    monkeypatch.setattr(reader, "_parse_line", lambda *args, **kwargs: record)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Diagnostics must not be built when disabled")

    monkeypatch.setattr(reader, "_build_line_diagnostic", fail_if_called)
    result = reader.read(path, source_cutoff=date(2026, 10, 2), diagnostic_mode=False)
    assert result.records == (record,)
    assert result.accepted_count == 1
    assert result.rejected_count == 0
    assert "trace" not in result.diagnostics


def test_explicit_diagnostic_vector_read_still_builds_trace(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "VectorPiPCA_20261002.txt"
    path.write_text("sample vector row\n", encoding="utf-8")
    reader = InstitutionalPiPCAVectorReader()
    record = _sample_record()
    monkeypatch.setattr(reader, "_parse_line", lambda *args, **kwargs: record)
    result = reader.read(path, source_cutoff=date(2026, 10, 2), diagnostic_mode=True)
    assert result.records == (record,)
    assert result.accepted_count == 1
    assert result.diagnostics["trace"]["records_valid"] == 1
    assert len(result.diagnostics["trace"]["line_diagnostics"]) == 1
