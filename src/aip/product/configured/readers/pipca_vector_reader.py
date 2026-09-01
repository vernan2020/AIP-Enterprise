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
        self,
        line: str,
        *,
        source_cutoff: date | None,
        source_line: int,
    ) -> InstitutionalVectorRecord | None:
        """
        Parse a PiPCA vector record.

        Supports two institutional layouts:

        1. Fixed-income / dated instruments:
           issuer + mnemonic + series + maturity + financial fields.

        2. Non-maturity investment-fund instruments:
           identifier + financial fields, without maturity date.

        The second layout is required for records such as:

            PRSFI + fiprc + PRSFI
        """

        if not line.strip():
            return None

        normalized_line = line.strip()

        if len(normalized_line) < 10:
            raise PiPCAParseError(
                "line too short",
                line=line,
                source_line=source_line,
                branch="length-check",
            )

        maturity_match = re.search(
            r"\d{2}/\d{2}/\d{4}",
            normalized_line,
        )

        # ========================================================
        # DATED / TRADITIONAL PiPCA RECORD
        # ========================================================

        if maturity_match is not None:

            issuer = self._extract_token(
                normalized_line,
                0,
                4,
            )

            instrument_type_or_mnemonic = self._extract_mnemonic(normalized_line)

            series_or_security_code = self._extract_series(normalized_line)

            maturity_date_field = maturity_match.group(0)

            financial_tokens = normalized_line[maturity_match.end() :].strip().split()

            coupon_or_reference_value = self._decimal_from_token(
                financial_tokens,
                0,
            )

            market_price = self._decimal_from_token(
                financial_tokens,
                1,
            )

            market_yield = self._decimal_from_token(
                financial_tokens,
                2,
            )

            spread_or_auxiliary_value = self._decimal_from_token(
                financial_tokens,
                3,
            )

            record_status = financial_tokens[4] if len(financial_tokens) > 4 else ""

            maturity_date = self._parse_date(maturity_date_field)

        # ========================================================
        # NON-MATURITY / FUND PiPCA RECORD
        # ========================================================

        else:

            try:
                (
                    issuer,
                    instrument_type_or_mnemonic,
                    series_or_security_code,
                    financial_tokens,
                ) = self._parse_non_maturity_layout(normalized_line)
            except PiPCAParseError as exc:
                # A traditional fixed-income identifier can be structurally
                # recognizable even when its mandatory maturity field is
                # absent. Preserve that distinction in diagnostics instead
                # of misclassifying it as an unsupported fund layout.
                issuer_probe = self._extract_issuer(normalized_line)
                mnemonic_probe = self._extract_mnemonic(normalized_line)
                series_probe = self._extract_series(normalized_line)
                if issuer_probe and mnemonic_probe and series_probe:
                    raise PiPCAParseError(
                        "missing maturity",
                        line=line,
                        source_line=source_line,
                        branch="maturity-scan",
                        field_widths=(len(normalized_line),),
                        raw_identifier=self._extract_raw_identifier(
                            normalized_line=normalized_line
                        ),
                    ) from exc
                raise

            maturity_date = None

            # Institutional non-maturity PiPCA layout:
            #
            # reference | auxiliary | yield | market price | status

            coupon_or_reference_value = self._decimal_from_token(
                financial_tokens,
                0,
            )

            spread_or_auxiliary_value = self._decimal_from_token(
                financial_tokens,
                1,
            )

            market_yield = self._decimal_from_token(
                financial_tokens,
                2,
            )

            market_price = self._decimal_from_token(
                financial_tokens,
                3,
            )

            record_status = financial_tokens[4] if len(financial_tokens) > 4 else ""

        # ========================================================
        # VALIDATION
        # ========================================================

        if not issuer and not instrument_type_or_mnemonic and not series_or_security_code:
            raise PiPCAParseError(
                "empty record",
                line=line,
                source_line=source_line,
                branch="empty-record",
                field_widths=(len(normalized_line),),
                raw_identifier="",
            )

        if not issuer or not instrument_type_or_mnemonic or not series_or_security_code:
            raise PiPCAParseError(
                "unsupported layout",
                line=line,
                source_line=source_line,
                branch="field-scan",
                field_widths=(len(normalized_line),),
                raw_identifier=(normalized_line[:30]),
            )

        if len(series_or_security_code) < 2:
            raise PiPCAParseError(
                "combined product-series parse failure",
                line=line,
                source_line=source_line,
                branch="series-split",
                field_widths=(len(normalized_line),),
                raw_identifier=(normalized_line[:30]),
            )

        isin_if_present = ""

        if "isin" in normalized_line.lower() or (
            len(normalized_line) > 30 and normalized_line[20:30].isdigit()
        ):
            isin_if_present = self._extract_token(
                normalized_line,
                20,
                36,
            )

        return InstitutionalVectorRecord(
            issuer=self._clean_text(issuer),
            instrument_type_or_mnemonic=(self._clean_text(instrument_type_or_mnemonic)),
            series_or_security_code=(self._clean_text(series_or_security_code)),
            normalized_issuer_key=(self._normalize_key(issuer)),
            normalized_series_key=(self._normalize_key(series_or_security_code)),
            isin_if_present=(isin_if_present),
            maturity_date_if_present=(maturity_date),
            coupon_or_reference_value=(coupon_or_reference_value),
            market_price=(market_price),
            market_yield=(market_yield),
            spread_or_auxiliary_value=(spread_or_auxiliary_value),
            record_status=self._clean_text(record_status),
            source_cutoff=(source_cutoff),
            source_line=(source_line),
        )

    def _parse_non_maturity_layout(
        self,
        line: str,
    ) -> tuple[
        str,
        str,
        str,
        list[str],
    ]:
        """
        Parse PiPCA instruments without maturity.

        The line is separated into:

            combined identifier
            five financial tokens

        The institutional product mnemonic has five characters.

        For fund records such as:

            PRSFI fiprc PRSFI

        the issuer is five characters and the series is equal
        to the issuer.

        A four-character issuer remains the default fallback
        for compatibility with the traditional PiPCA layout.
        """

        match = re.match(
            r"^(?P<identifier>\S+)\s+"
            r"(?P<f0>[+-]?\d+(?:\.\d+)?)\s+"
            r"(?P<f1>[+-]?\d+(?:\.\d+)?)\s+"
            r"(?P<f2>[+-]?\d+(?:\.\d+)?)\s+"
            r"(?P<f3>[+-]?\d+(?:\.\d+)?)\s+"
            r"(?P<f4>\S+)\s*$",
            line,
        )

        if match is None:
            raise PiPCAParseError(
                "unsupported non-maturity layout",
                line=line,
                branch="non-maturity-layout",
                raw_identifier=(line[:40]),
            )

        identifier = match.group("identifier")

        financial_tokens = [
            match.group("f0"),
            match.group("f1"),
            match.group("f2"),
            match.group("f3"),
            match.group("f4"),
        ]

        # --------------------------------------------------------
        # Candidate A:
        # five-character issuer + five-character product
        # --------------------------------------------------------

        issuer_5 = identifier[:5] if len(identifier) >= 15 else ""

        product_5 = identifier[5:10] if len(identifier) >= 15 else ""

        series_5 = identifier[10:] if len(identifier) >= 15 else ""

        # Fund vectors observed institutionally use the fund
        # mnemonic as issuer and series, e.g. PRSFI ... PRSFI.

        if issuer_5 and series_5 and self._normalize_key(issuer_5) == self._normalize_key(series_5):
            return (
                issuer_5,
                product_5,
                series_5,
                financial_tokens,
            )

        # --------------------------------------------------------
        # Candidate B:
        # traditional four-character issuer
        # --------------------------------------------------------

        if len(identifier) >= 11:

            issuer_4 = identifier[:4]

            product_4 = identifier[4:9]

            series_4 = identifier[9:]

            if issuer_4 and product_4 and series_4:
                return (
                    issuer_4,
                    product_4,
                    series_4,
                    financial_tokens,
                )

        raise PiPCAParseError(
            "non-maturity identifier parse failure",
            line=line,
            branch="non-maturity-identifier",
            raw_identifier=(identifier),
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
        """
        Extract PiPCA product mnemonic and security series.

        PiPCA contains both dated instruments and instruments without an
        explicit maturity date.  For dated instruments, the maturity date
        marks the end of the combined product/series identifier.

        For non-dated instruments, the identifier is obtained from the
        fixed-width prefix before the financial section.  This preserves
        support for records such as:

            PRSFI + fiprc + PRSFI

        without requiring a synthetic maturity date.
        """
        remainder = line[4:] if len(line) > 4 else ""
        if not remainder:
            return "", ""

        maturity_match = re.search(r"\d{2}/\d{2}/\d{4}", remainder)

        if maturity_match is not None:
            combined_field = remainder[: maturity_match.start()].strip()
        else:
            combined_field = self._extract_non_maturity_identifier(remainder)

        if not combined_field:
            return "", ""

        product_code = self._clean_text(combined_field[:5])
        series_code = self._clean_text(combined_field[5:])

        if not product_code and not series_code:
            return "", ""

        return product_code, series_code

    def _extract_non_maturity_identifier(self, remainder: str) -> str:
        """
        Extract the product+series identifier when PiPCA omits maturity.

        Institutional PiPCA records use a five-character product mnemonic.
        The series immediately follows it.  The financial section begins
        when the first numeric financial token is encountered.

        Example:

            fiprcPRSFI          0.000 0.000000 0.000 1013.100000 0

        becomes:

            fiprcPRSFI
        """
        stripped = remainder.strip()
        if not stripped:
            return ""

        financial_match = re.search(
            r"\s+(?=[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s)",
            stripped,
        )

        if financial_match is not None:
            return stripped[: financial_match.start()].strip()

        return stripped

    def _extract_raw_identifier(self, normalized_line: str) -> str:
        return self._clean_text(self._extract_token(normalized_line, 4, len(normalized_line)))

    def _extract_maturity_date_field(self, line: str) -> str:
        match = re.search(r"\d{2}/\d{2}/\d{4}", line)
        if not match:
            return ""
        return match.group(0)

    def _extract_financial_tokens(self, line: str) -> list[str]:
        """
        Extract financial fields from dated and non-dated PiPCA records.
        """
        maturity_match = re.search(r"\d{2}/\d{2}/\d{4}", line)

        if maturity_match is not None:
            return line[maturity_match.end() :].strip().split()

        remainder = line[4:] if len(line) > 4 else ""
        identifier = self._extract_non_maturity_identifier(remainder)

        if not identifier:
            return []

        identifier_position = remainder.find(identifier)
        if identifier_position < 0:
            return []

        financial_start = identifier_position + len(identifier)
        financial_text = remainder[financial_start:].strip()

        return financial_text.split() if financial_text else []

    def _decimal_from_token(self, tokens: list[str], index: int) -> Decimal | None:
        if index >= len(tokens):
            return None
        token = tokens[index].strip()
        if not token:
            return None
        try:
            return Decimal(token)
        except InvalidOperation:
            return None

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
