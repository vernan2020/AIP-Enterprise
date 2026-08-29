from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aip.product.configured.readers.pipca_vector_reader import (
    InstitutionalPiPCAVectorReader,
    InstitutionalPiPCAVectorReadResult,
    InstitutionalVectorRecord,
)


@dataclass(frozen=True, slots=True)
class InstitutionalVectorRow:
    row_id: str
    instrument_id: str
    price: float
    valuation_date: date


class InstitutionalVectorReader(InstitutionalPiPCAVectorReader):
    """Backward-compatible PiPCA vector reader for the historical test contract."""

    def read(self, path: str | Path, *, source_cutoff: date | None = None, diagnostic_mode: bool = False) -> list[InstitutionalVectorRow]:
        del source_cutoff, diagnostic_mode
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"PiPCA vector file does not exist: {file_path}")

        encoding = self._detect_encoding(file_path)
        content = file_path.read_text(encoding=encoding)
        rows: list[InstitutionalVectorRow] = []
        lines = [line for line in content.splitlines() if line.strip()]
        for line_number, raw_line in enumerate(lines, start=1):
            if line_number == 1 and raw_line.lower().startswith("row_id"):
                continue
            if ";" not in raw_line:
                raise ValueError("malformed")

            columns = [column.strip() for column in raw_line.split(";")]
            if len(columns) != 4:
                raise ValueError("malformed")

            row_id, instrument_id, price_text, valuation_date_text = columns
            if not row_id or not instrument_id or not price_text or not valuation_date_text:
                raise ValueError("malformed")

            try:
                normalized_price = price_text.replace(".", "").replace(",", ".")
                price_value = Decimal(normalized_price)
            except InvalidOperation as exc:
                raise ValueError("malformed") from exc

            try:
                valuation_date = datetime.strptime(valuation_date_text, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError("malformed") from exc

            rows.append(
                InstitutionalVectorRow(
                    row_id=row_id,
                    instrument_id=instrument_id,
                    price=float(price_value),
                    valuation_date=valuation_date,
                )
            )

        return rows


__all__ = [
    "InstitutionalPiPCAVectorReadResult",
    "InstitutionalPiPCAVectorReader",
    "InstitutionalVectorRecord",
    "InstitutionalVectorReader",
    "InstitutionalVectorRow",
]
