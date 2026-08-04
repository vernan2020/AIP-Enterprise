from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class InstitutionalVectorRecord:
    issuer: str
    instrument_type_or_mnemonic: str
    series_or_security_code: str
    isin_if_present: str
    maturity_date_if_present: date | None
    coupon_or_reference_value: Decimal | None
    market_price: Decimal | None
    market_yield: Decimal | None
    spread_or_auxiliary_value: Decimal | None
    record_status: str
    source_cutoff: date | None
    source_line: int


@dataclass(frozen=True, slots=True)
class InstitutionalPiPCAVectorReadResult:
    path: str
    encoding: str
    source_cutoff: date | None
    records: tuple[InstitutionalVectorRecord, ...]
    accepted_count: int
    rejected_count: int
    diagnostics: dict[str, Any]


class InstitutionalPiPCAVectorReader:
    _MAX_DIAGNOSTIC_TRACE_ENTRIES = 20

    def read(self, path: str | Path, *, source_cutoff: date | None = None, diagnostic_mode: bool = False) -> InstitutionalPiPCAVectorReadResult:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"PiPCA vector file does not exist: {file_path}")

        encoding = self._detect_encoding(file_path)
        content = file_path.read_text(encoding=encoding)
        lines = [line.rstrip("\n") for line in content.splitlines() if line.strip()]
        records: list[InstitutionalVectorRecord] = []
        rejected_count = 0
        record_trace: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(lines, start=1):
            try:
                record = self._parse_line(raw_line, source_cutoff=source_cutoff, source_line=line_number)
            except ValueError as exc:
                rejected_count += 1
                if diagnostic_mode:
                    record_trace.append({"line": line_number, "status": "discarded", "reason": str(exc), "isin": None})
                continue
            if record is not None:
                records.append(record)
                if diagnostic_mode:
                    record_trace.append({"line": line_number, "status": "accepted", "reason": "parsed", "isin": record.isin_if_present or None})
        trace_payload = None
        if diagnostic_mode:
            trace_payload = {
                "source_file": self._safe_diagnostic_reference(file_path),
                "records_read": len(lines),
                "records_valid": len(records),
                "records_discarded": rejected_count,
                "isin_found": [record.isin_if_present for record in records if record.isin_if_present],
                "record_trace": record_trace[-self._MAX_DIAGNOSTIC_TRACE_ENTRIES :],
            }

        diagnostics = {
            "line_count": len(lines),
            "layout": "positional-fixed-width",
            "source_reference": self._safe_diagnostic_reference(file_path),
        }
        if trace_payload is not None:
            diagnostics["trace"] = trace_payload
        return InstitutionalPiPCAVectorReadResult(
            path=str(file_path),
            encoding=encoding,
            source_cutoff=source_cutoff,
            records=tuple(records),
            accepted_count=len(records),
            rejected_count=rejected_count,
            diagnostics=diagnostics,
        )

    def _detect_encoding(self, path: Path) -> str:
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            return encoding
        return "utf-8"

    def _safe_diagnostic_reference(self, path: Path | str | None) -> str:
        if not path:
            return ""
        path_text = str(path)
        if not path_text:
            return ""
        candidate = Path(path_text)
        if not candidate.name:
            return ""
        return candidate.name

    def _parse_line(self, line: str, *, source_cutoff: date | None, source_line: int) -> InstitutionalVectorRecord | None:
        if not line.strip():
            return None
        normalized_line = line.strip()
        if len(normalized_line) < 10:
            raise ValueError("line too short")

        issuer = self._extract_issuer(normalized_line)
        instrument_type_or_mnemonic = self._extract_mnemonic(normalized_line)
        series_or_security_code = self._extract_series(normalized_line)
        maturity_date_field = self._extract_maturity_date_field(normalized_line)
        coupon_or_reference_value = self._extract_decimal(normalized_line, 48, 60)
        market_price = self._extract_decimal(normalized_line, 60, 72)
        market_yield = self._extract_decimal(normalized_line, 72, 84)
        spread_or_auxiliary_value = self._extract_decimal(normalized_line, 84, 96)
        record_status = self._extract_token(normalized_line, 96, 104)

        maturity_date = self._parse_date(maturity_date_field)
        if not issuer and not instrument_type_or_mnemonic and not series_or_security_code:
            raise ValueError("empty record")
        if len(series_or_security_code) < 2 and not issuer:
            raise ValueError("malformed record")
        if not re.search(r"\d{2}/\d{2}/\d{4}", normalized_line):
            raise ValueError("malformed record")

        isin_if_present = ""
        if "isin" in normalized_line.lower() or len(normalized_line) > 30 and normalized_line[20:30].isdigit():
            isin_if_present = self._extract_token(normalized_line, 20, 36)

        return InstitutionalVectorRecord(
            issuer=self._clean_text(issuer),
            instrument_type_or_mnemonic=self._clean_text(instrument_type_or_mnemonic),
            series_or_security_code=self._clean_text(series_or_security_code),
            isin_if_present=isin_if_present,
            maturity_date_if_present=maturity_date,
            coupon_or_reference_value=coupon_or_reference_value,
            market_price=market_price,
            market_yield=market_yield,
            spread_or_auxiliary_value=spread_or_auxiliary_value,
            record_status=self._clean_text(record_status),
            source_cutoff=source_cutoff,
            source_line=source_line,
        )

    def _extract_token(self, line: str, start: int, end: int) -> str:
        if start >= len(line):
            return ""
        return line[start:end].strip()

    def _extract_issuer(self, line: str) -> str:
        return self._extract_token(line, 0, 4)

    def _extract_mnemonic(self, line: str) -> str:
        return self._extract_token(line, 4, 10)

    def _extract_series(self, line: str) -> str:
        prefix = self._extract_token(line, 10, 12)
        remainder = line[12:].strip()
        if not remainder:
            return prefix
        match = re.search(r"\d{2}/\d{2}/\d{4}", remainder)
        if match:
            remainder = remainder[:match.start()].strip()
        if not remainder:
            return prefix
        combined = f"{prefix}{remainder}".strip()
        return combined if combined else ""

    def _extract_maturity_date_field(self, line: str) -> str:
        match = re.search(r"\d{2}/\d{2}/\d{4}", line)
        if not match:
            return ""
        return match.group(0)

    def _extract_decimal(self, line: str, start: int, end: int) -> Decimal | None:
        token = self._extract_token(line, start, end)
        if not token:
            return None
        try:
            return Decimal(token)
        except InvalidOperation:
            return None

    def _clean_text(self, value: str) -> str:
        text = unicodedata.normalize("NFKD", value)
        ascii_text = text.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", ascii_text).strip()

    def _parse_date(self, value: str) -> date | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return datetime.strptime(cleaned, "%d/%m/%Y").date()
        except ValueError:
            return None
