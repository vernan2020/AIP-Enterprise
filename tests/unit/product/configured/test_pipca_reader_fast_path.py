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


def test_normal_read_skips_diagnostics(tmp_path, monkeypatch) -> None:
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


def test_explicit_diagnostic_read_preserves_trace(tmp_path, monkeypatch) -> None:
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


def test_vector_is_read_only_once(tmp_path, monkeypatch) -> None:
    path = tmp_path / "VectorPiPCA_20261002.txt"
    path.write_bytes(b"first line\r\nsecond line\r\n")
    reader = InstitutionalPiPCAVectorReader()
    record = _sample_record()
    parsed: list[str] = []

    def parse_line(line, **kwargs):
        parsed.append(line)
        return record

    monkeypatch.setattr(reader, "_parse_line", parse_line)
    original_read_bytes = type(path).read_bytes
    reads = []

    def tracked_read_bytes(candidate):
        reads.append(candidate)
        return original_read_bytes(candidate)

    monkeypatch.setattr(type(path), "read_bytes", tracked_read_bytes)
    result = reader.read(path, source_cutoff=date(2026, 10, 2))
    assert reads == [path]
    assert parsed == ["first line", "second line"]
    assert result.accepted_count == 2


def test_vector_encoding_detection_preserves_original_precedence() -> None:
    reader = InstitutionalPiPCAVectorReader()
    cases = (
        (b"abc", "utf-8-sig", "abc"),
        (b"\xef\xbb\xbfabc", "utf-8-sig", "abc"),
        (b"caf\xe9", "cp1252", "café"),
        (b"caf\x81", "latin-1", "caf\x81"),
    )
    for raw, expected_encoding, expected_content in cases:
        encoding, content = reader._decode_vector_bytes(raw)
        assert encoding == expected_encoding
        assert content == expected_content
