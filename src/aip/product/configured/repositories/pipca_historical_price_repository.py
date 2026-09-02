from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from aip.domain.portfolio.risk.historical_price_series import HistoricalPriceObservation
from aip.product.configured.readers.pipca_vector_reader import (
    InstitutionalPiPCAVectorReader,
    InstitutionalVectorRecord,
)


@dataclass(frozen=True, slots=True)
class PiPCAHistoricalLookupResult:
    security_key: str
    cutoff_date: date
    observations: tuple[HistoricalPriceObservation, ...]
    vector_dates_available: int
    files_read: int
    matched_dates: int
    status: str
    diagnostic: str | None = None


class PiPCAHistoricalPriceRepository:
    """Historical PiPCA repository with lazy file and record indexes.

    Files are discovered once per repository instance and parsed only as needed.
    Parsed records are cached by path, preserving the latency improvements of
    repeated VeR navigation while keeping PiPCA as the primary source.
    """

    DEFAULT_LIMIT = 521
    _DATE_RE = re.compile(r"(?:VectorPiPCA[_-]?)(\d{4})(\d{2})(\d{2})", re.I)

    def __init__(
        self,
        investment_root: str | Path,
        *,
        reader: InstitutionalPiPCAVectorReader | None = None,
    ) -> None:
        root = Path(investment_root)
        nested = root / "Inversiones"
        self._investment_root = nested if nested.is_dir() else root
        self._reader = reader or InstitutionalPiPCAVectorReader()
        self._file_index_cache: dict[date, Path] | None = None
        self._record_cache: dict[Path, tuple[InstitutionalVectorRecord, ...]] = {}
        self._series_index_cache: dict[tuple[Path, str], tuple[InstitutionalVectorRecord, ...]] = {}

    def available_vector_dates(self, *, cutoff_date: date) -> tuple[date, ...]:
        return tuple(day for day in sorted(self._file_index()) if day <= cutoff_date)

    def get_observations(
        self,
        *,
        series: str = "",
        issuer: str = "",
        product_code: str = "",
        maturity_date: date | None = None,
        cutoff_date: date,
        limit: int = DEFAULT_LIMIT,
    ) -> PiPCAHistoricalLookupResult:
        if limit <= 0:
            raise ValueError("limit must be positive")
        normalized_series = self._normalize(series)
        normalized_issuer = self._normalize(issuer)
        normalized_product = self._normalize(product_code)
        security_key = normalized_series or "|".join(
            value for value in (normalized_issuer, normalized_product) if value
        )

        dates = self.available_vector_dates(cutoff_date=cutoff_date)
        observations: list[HistoricalPriceObservation] = []
        files_read = 0
        ambiguous_dates = 0

        for vector_date in reversed(dates):
            if len(observations) >= limit:
                break
            path = self._file_index()[vector_date]
            records = self._records_for_series(path, normalized_series)
            files_read += 1
            candidates = self._matching_records(
                records=records,
                normalized_series=normalized_series,
                normalized_issuer=normalized_issuer,
                normalized_product=normalized_product,
                maturity_date=maturity_date,
            )
            selected, ambiguous = self._select_candidate(candidates)
            if ambiguous:
                ambiguous_dates += 1
            if selected is None or selected.market_price is None or selected.market_price <= 0:
                continue
            observations.append(
                HistoricalPriceObservation(
                    valuation_date=vector_date,
                    market_price=Decimal(selected.market_price),
                    source=path.name,
                    synthetic=False,
                )
            )

        observations.reverse()
        status = (
            "COMPLETE_REAL_HISTORY"
            if len(observations) >= limit
            else "PARTIAL_REAL_HISTORY" if observations else "PIPCA_HISTORY_UNAVAILABLE"
        )
        diagnostic = None
        if ambiguous_dates:
            diagnostic = f"{ambiguous_dates} PiPCA dates contained ambiguous candidate prices"
        elif not observations:
            diagnostic = "No PiPCA observations matched the requested security"

        return PiPCAHistoricalLookupResult(
            security_key=security_key,
            cutoff_date=cutoff_date,
            observations=tuple(observations[-limit:]),
            vector_dates_available=len(dates),
            files_read=files_read,
            matched_dates=len(observations),
            status=status,
            diagnostic=diagnostic,
        )

    def _file_index(self) -> dict[date, Path]:
        if self._file_index_cache is not None:
            return self._file_index_cache
        discovered: dict[date, Path] = {}
        if self._investment_root.is_dir():
            for path in self._investment_root.rglob("*.txt"):
                if "vector" not in {part.casefold() for part in path.parts}:
                    continue
                match = self._DATE_RE.search(path.stem)
                if match is None:
                    continue
                try:
                    vector_date = date(
                        int(match.group(1)), int(match.group(2)), int(match.group(3))
                    )
                except ValueError:
                    continue
                current = discovered.get(vector_date)
                if current is None or path.stat().st_mtime_ns > current.stat().st_mtime_ns:
                    discovered[vector_date] = path
        self._file_index_cache = discovered
        return discovered

    def _records(self, path: Path) -> tuple[InstitutionalVectorRecord, ...]:
        cached = self._record_cache.get(path)
        if cached is not None:
            return cached
        vector_date = next(
            (day for day, candidate in self._file_index().items() if candidate == path),
            None,
        )
        result = self._reader.read(path, source_cutoff=vector_date, diagnostic_mode=False)
        records = tuple(result.records)
        self._record_cache[path] = records
        return records

    def _records_for_series(
        self,
        path: Path,
        normalized_series: str,
    ) -> tuple[InstitutionalVectorRecord, ...]:
        key = (path, normalized_series)
        cached = self._series_index_cache.get(key)
        if cached is not None:
            return cached
        records = self._records(path)
        if normalized_series:
            filtered = tuple(
                record
                for record in records
                if self._normalize(record.series_or_security_code) == normalized_series
                or self._normalize(record.normalized_series_key) == normalized_series
            )
        else:
            filtered = records
        self._series_index_cache[key] = filtered
        return filtered

    @classmethod
    def _matching_records(
        cls,
        *,
        records: tuple[InstitutionalVectorRecord, ...],
        normalized_series: str,
        normalized_issuer: str,
        normalized_product: str,
        maturity_date: date | None,
    ) -> list[InstitutionalVectorRecord]:
        scored: list[tuple[int, InstitutionalVectorRecord]] = []
        for record in records:
            if record.market_price is None or record.market_price <= 0:
                continue
            record_series = cls._normalize(record.series_or_security_code)
            record_issuer = cls._normalize(record.issuer)
            record_product = cls._normalize(record.instrument_type_or_mnemonic)
            score = 0
            if normalized_series:
                if record_series != normalized_series:
                    continue
                score += 8
            if normalized_issuer and record_issuer == normalized_issuer:
                score += 4
            elif normalized_issuer and normalized_series == "":
                continue
            if normalized_product and record_product == normalized_product:
                score += 2
            if maturity_date is not None:
                if record.maturity_date_if_present == maturity_date:
                    score += 4
                elif record.maturity_date_if_present is not None:
                    continue
            elif record.maturity_date_if_present is None:
                score += 1
            scored.append((score, record))
        if not scored:
            return []
        best = max(score for score, _ in scored)
        return [record for score, record in scored if score == best]

    @staticmethod
    def _select_candidate(
        candidates: list[InstitutionalVectorRecord],
    ) -> tuple[InstitutionalVectorRecord | None, bool]:
        if not candidates:
            return None, False
        prices = {
            candidate.market_price for candidate in candidates if candidate.market_price is not None
        }
        if len(prices) > 1:
            return None, True
        return candidates[0], False

    @staticmethod
    def _normalize(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]", "", ascii_text.casefold())
