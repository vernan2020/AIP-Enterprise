from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class PiPCAParseError(ValueError):
    """Raised when a PiPCA line cannot be parsed into a vector record."""

    def __init__(
        self,
        reason: str,
        *,
        line: str,
        source_line: int | None = None,
        branch: str | None = None,
        field_widths: tuple[int, ...] | None = None,
        raw_identifier: str | None = None,
    ) -> None:
        self.reason = reason
        self.line = line
        self.source_line = source_line
        self.branch = branch
        self.field_widths = field_widths or ()
        self.raw_identifier = raw_identifier
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class InstitutionalVectorRecord:
    issuer: str
    instrument_type_or_mnemonic: str
    series_or_security_code: str
    normalized_issuer_key: str
    normalized_series_key: str
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

    def read(
        self, path: str | Path, *, source_cutoff: date | None = None, diagnostic_mode: bool = False
    ) -> InstitutionalPiPCAVectorReadResult:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"PiPCA vector file does not exist: {file_path}")

        encoding = self._detect_encoding(file_path)
        content = file_path.read_text(encoding=encoding)
        lines = [line.rstrip("\n") for line in content.splitlines() if line.strip()]
        records: list[InstitutionalVectorRecord] = []
        rejected_count = 0
        rejected_reason_counts: dict[str, int] = {}
        record_trace: list[dict[str, Any]] = []
        accepted_records: list[dict[str, Any]] = []
        line_diagnostics: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(lines, start=1):
            line_diagnostic = self._build_line_diagnostic(raw_line, source_line=line_number)
            if diagnostic_mode:
                line_diagnostics.append(line_diagnostic)
            try:
                record = self._parse_line(
                    raw_line, source_cutoff=source_cutoff, source_line=line_number
                )
            except PiPCAParseError as exc:
                rejected_count += 1
                reason = exc.reason
                rejected_reason_counts[reason] = rejected_reason_counts.get(reason, 0) + 1
                if diagnostic_mode:
                    line_diagnostic.update(
                        {
                            "status": "rejected",
                            "reason": reason,
                            "parser_branch": exc.branch,
                            "raw_identifier": exc.raw_identifier,
                        }
                    )
                    record_trace.append(
                        {
                            "line": line_number,
                            "status": "discarded",
                            "reason": reason,
                            "branch": exc.branch,
                            "field_widths": list(exc.field_widths),
                            "raw_identifier": exc.raw_identifier,
                            "isin": None,
                        }
                    )
                continue
            except ValueError as exc:
                rejected_count += 1
                reason = str(exc)
                rejected_reason_counts[reason] = rejected_reason_counts.get(reason, 0) + 1
                if diagnostic_mode:
                    line_diagnostic.update(
                        {
                            "status": "rejected",
                            "reason": reason,
                            "parser_branch": None,
                            "raw_identifier": None,
                        }
                    )
                    record_trace.append(
                        {
                            "line": line_number,
                            "status": "discarded",
                            "reason": reason,
                            "branch": None,
                            "field_widths": [],
                            "raw_identifier": None,
                            "isin": None,
                        }
                    )
                continue
            if record is not None:
                records.append(record)
                if diagnostic_mode:
                    line_diagnostic.update(
                        {
                            "status": "accepted",
                            "reason": "parsed",
                            "parser_branch": "accepted",
                            "raw_identifier": self._extract_raw_identifier(
                                normalized_line=raw_line
                            ),
                        }
                    )
                    diagnostics_entry = {
                        "line": record.source_line,
                        "status": "accepted",
                        "reason": "parsed",
                        "issuer": record.issuer,
                        "mnemonic": record.instrument_type_or_mnemonic,
                        "series_or_security_code": record.series_or_security_code,
                        "maturity_date": (
                            record.maturity_date_if_present.isoformat()
                            if record.maturity_date_if_present
                            else None
                        ),
                        "normalized_series_key": record.normalized_series_key,
                        "normalized_issuer_key": record.normalized_issuer_key,
                        "isin": record.isin_if_present or None,
                        "raw_identifier": self._extract_raw_identifier(normalized_line=raw_line),
                    }
                    record_trace.append(diagnostics_entry)
                    accepted_records.append(diagnostics_entry)
            if diagnostic_mode and len(line_diagnostics) > 0:
                line_diagnostics[-1] = line_diagnostic
        trace_payload = None
        if diagnostic_mode:
            trace_payload = {
                "source_file": self._safe_diagnostic_reference(file_path),
                "records_read": len(lines),
                "records_valid": len(records),
                "records_discarded": rejected_count,
                "rejected_reason_counts": rejected_reason_counts,
                "isin_found": [
                    record.isin_if_present for record in records if record.isin_if_present
                ],
                "accepted_records": accepted_records,
                "line_diagnostics": line_diagnostics,
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

    def _build_line_diagnostic(self, raw_line: str, *, source_line: int) -> dict[str, Any]:
        maturity_match = re.search(r"\d{2}/\d{2}/\d{4}", raw_line)
        maturity_start = maturity_match.start() if maturity_match else None
        maturity_end = maturity_match.end() if maturity_match else None
        maturity_text = maturity_match.group(0) if maturity_match else ""
        combined_field_end = maturity_start if maturity_start is not None else len(raw_line)
        issuer = self._extract_issuer(raw_line)
        product_code = self._extract_mnemonic(raw_line)
        series_code = self._extract_series(raw_line)
        parsed_maturity = self._parse_date(maturity_text)
        return {
            "line": source_line,
            "raw_line_length": len(raw_line),
            "raw_line": raw_line,
            "masked_raw_line": self._mask_text(raw_line),
            "parser_branch": "pending",
            "issuer_slice": {"start": 0, "end": 4, "text": raw_line[0:4]},
            "product_series_slice": {
                "start": 4,
                "end": combined_field_end,
                "text": raw_line[4:combined_field_end],
            },
            "maturity_slice": {"start": maturity_start, "end": maturity_end, "text": maturity_text},
            "parsed_issuer": issuer,
            "parsed_product": product_code,
            "parsed_series": series_code,
            "raw_maturity": maturity_text,
            "parsed_maturity": parsed_maturity.isoformat() if parsed_maturity else None,
            "status": "pending",
            "reason": "pending",
            "raw_identifier": self._extract_raw_identifier(normalized_line=raw_line),
        }

    def _mask_text(self, text: str) -> str:
        return "".join(ch if ch.isspace() else "*" for ch in text)

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

    def _parse_line(
        self, line: str, *, source_cutoff: date | None, source_line: int
    ) -> InstitutionalVectorRecord | None:
        if not line.strip():
            return None
        normalized_line = line.strip()
        if len(normalized_line) < 10:
            raise PiPCAParseError(
                "line too short", line=line, source_line=source_line, branch="length-check"
            )

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
            raise PiPCAParseError(
                "empty record",
                line=line,
                source_line=source_line,
                branch="empty-record",
                field_widths=(len(normalized_line),),
                raw_identifier="",
            )
        if not re.search(r"\d{2}/\d{2}/\d{4}", normalized_line):
            raise PiPCAParseError(
                "missing maturity",
                line=line,
                source_line=source_line,
                branch="maturity-scan",
                field_widths=(len(normalized_line),),
                raw_identifier=normalized_line[:20],
            )
        if not issuer or not instrument_type_or_mnemonic or not series_or_security_code:
            raise PiPCAParseError(
                "unsupported layout",
                line=line,
                source_line=source_line,
                branch="field-scan",
                field_widths=(len(normalized_line),),
                raw_identifier=normalized_line[:20],
            )
        if len(series_or_security_code) < 2:
            raise PiPCAParseError(
                "combined product-series parse failure",
                line=line,
                source_line=source_line,
                branch="series-split",
                field_widths=(len(normalized_line),),
                raw_identifier=normalized_line[:20],
            )

        isin_if_present = ""
        if (
            "isin" in normalized_line.lower()
            or len(normalized_line) > 30
            and normalized_line[20:30].isdigit()
        ):
            isin_if_present = self._extract_token(normalized_line, 20, 36)

        return InstitutionalVectorRecord(
            issuer=self._clean_text(issuer),
            instrument_type_or_mnemonic=self._clean_text(instrument_type_or_mnemonic),
            series_or_security_code=self._clean_text(series_or_security_code),
            normalized_issuer_key=self._normalize_key(issuer),
            normalized_series_key=self._normalize_key(series_or_security_code),
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
        product_code, _ = self._extract_product_and_series(line)
        return product_code

    def _extract_series(self, line: str) -> str:
        _, series_code = self._extract_product_and_series(line)
        return series_code

    def _extract_product_and_series(self, line: str) -> tuple[str, str]:
        combined_field = self._extract_token(line, 4, len(line))
        if not combined_field:
            return "", ""

        match = re.search(r"\d{2}/\d{2}/\d{4}", combined_field)
        if match:
            combined_field = combined_field[: match.start()].strip()

        product_code = self._clean_text(combined_field[:5])
        series_code = self._clean_text(combined_field[5:])
        if not product_code and not series_code:
            return "", ""
        if not series_code and len(combined_field) > 5:
            series_code = self._clean_text(combined_field[5:])
        if not product_code and len(combined_field) > 5:
            product_code = self._clean_text(combined_field[:5])
        return product_code, series_code

    def _extract_raw_identifier(self, normalized_line: str) -> str:
        return self._clean_text(self._extract_token(normalized_line, 4, len(normalized_line)))

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

    def _normalize_key(self, value: str) -> str:
        text = self._clean_text(value)
        if not text:
            return ""
        return re.sub(r"\s+", "", text).casefold()

    def _parse_date(self, value: str) -> date | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return datetime.strptime(cleaned, "%d/%m/%Y").date()
        except ValueError:
            return None
