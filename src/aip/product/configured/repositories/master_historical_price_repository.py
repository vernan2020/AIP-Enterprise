from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aip.domain.portfolio.risk.historical_price_series import HistoricalPriceObservation
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)


@dataclass(frozen=True, slots=True)
class MasterHistoricalLookupResult:
    security_key: str
    requested_isin: str
    requested_series: str
    requested_issuer: str
    cutoff_date: date
    observations: tuple[HistoricalPriceObservation, ...]
    master_dates_available: int
    master_files_read: int
    matched_dates: int
    first_real_date: date | None
    last_real_date: date | None
    ambiguous_dates: int
    status: str
    diagnostic: str | None = None

    @property
    def observation_count(self) -> int:
        return len(self.observations)


class MasterHistoricalPriceRepository:
    """Historical master-price fallback with lazy discovery/read caches."""

    DEFAULT_LIMIT = 521
    _DATE_RE = re.compile(r"(?P<day>\d{1,2})-(?P<month>\d{1,2})-(?P<year>\d{4})")

    def __init__(
        self,
        investment_root: str | Path,
        *,
        reader: InstitutionalPortfolioMasterReader | None = None,
    ) -> None:
        root = Path(investment_root)
        nested = root / "Inversiones"
        self._investment_root = nested if nested.is_dir() else root
        self._reader = reader or InstitutionalPortfolioMasterReader()
        self._file_index_cache: dict[date, Path] | None = None
        self._position_cache: dict[Path, tuple[dict[str, Any], ...]] = {}

    def get_observations(
        self,
        *,
        isin: str = "",
        series: str = "",
        issuer: str = "",
        cutoff_date: date,
        limit: int = DEFAULT_LIMIT,
    ) -> MasterHistoricalLookupResult:
        if limit <= 0:
            raise ValueError("limit must be positive")
        normalized_isin = self._normalize_key(isin)
        normalized_series = self._normalize_key(series)
        normalized_issuer = self._normalize_key(issuer)
        security_key = normalized_isin or normalized_series
        files = [
            (day, path) for day, path in sorted(self._file_index().items()) if day <= cutoff_date
        ]
        observations: list[HistoricalPriceObservation] = []
        files_read = 0
        ambiguous_dates = 0

        for master_date, master_path in reversed(files):
            if len(observations) >= limit:
                break
            positions = self._read_master(master_path, master_date)
            files_read += 1
            matched, ambiguous = self._match_position(
                positions=positions,
                normalized_isin=normalized_isin,
                normalized_series=normalized_series,
                normalized_issuer=normalized_issuer,
            )
            if ambiguous:
                ambiguous_dates += 1
            if matched is None:
                continue
            price = self._market_price(matched)
            if price is None or price <= 0:
                continue
            observations.append(
                HistoricalPriceObservation(
                    valuation_date=master_date,
                    market_price=price,
                    source=master_path.name,
                    synthetic=False,
                )
            )

        observations.reverse()
        observation_tuple = tuple(observations[-limit:])
        first_real = observation_tuple[0].valuation_date if observation_tuple else None
        last_real = observation_tuple[-1].valuation_date if observation_tuple else None
        status = (
            "COMPLETE_REAL_HISTORY"
            if len(observation_tuple) >= limit
            else "PARTIAL_REAL_HISTORY" if observation_tuple else "MASTER_HISTORY_UNAVAILABLE"
        )
        diagnostic = None
        if ambiguous_dates:
            diagnostic = f"{ambiguous_dates} master dates contained ambiguous candidate prices"
        elif not observation_tuple:
            diagnostic = "No historical master-price observations matched the requested security"

        return MasterHistoricalLookupResult(
            security_key=security_key,
            requested_isin=isin,
            requested_series=series,
            requested_issuer=issuer,
            cutoff_date=cutoff_date,
            observations=observation_tuple,
            master_dates_available=len(files),
            master_files_read=files_read,
            matched_dates=len(observation_tuple),
            first_real_date=first_real,
            last_real_date=last_real,
            ambiguous_dates=ambiguous_dates,
            status=status,
            diagnostic=diagnostic,
        )

    def available_master_dates(self, *, cutoff_date: date) -> tuple[date, ...]:
        return tuple(day for day in sorted(self._file_index()) if day <= cutoff_date)

    def _file_index(self) -> dict[date, Path]:
        if self._file_index_cache is not None:
            return self._file_index_cache
        discovered: dict[date, Path] = {}
        if self._investment_root.is_dir():
            for path in self._investment_root.rglob("*.xls*"):
                if "maestro" not in {part.casefold() for part in path.parts}:
                    continue
                match = self._DATE_RE.search(path.stem)
                if match is None:
                    continue
                try:
                    master_date = date(
                        int(match.group("year")),
                        int(match.group("month")),
                        int(match.group("day")),
                    )
                except ValueError:
                    continue
                current = discovered.get(master_date)
                if (
                    current is None
                    or self._prefer_candidate(
                        current=current,
                        challenger=path,
                        valuation_date=master_date,
                    )
                    == path
                ):
                    discovered[master_date] = path
        self._file_index_cache = discovered
        return discovered

    def _read_master(self, path: Path, valuation_date: date) -> tuple[dict[str, Any], ...]:
        cached = self._position_cache.get(path)
        if cached is not None:
            return cached
        result = self._reader.read(
            path,
            valuation_date_override=valuation_date,
            diagnostic_mode=False,
        )
        positions = tuple(item for item in result.normalized_positions if isinstance(item, dict))
        self._position_cache[path] = positions
        return positions

    @classmethod
    def _match_position(
        cls,
        *,
        positions: tuple[dict[str, Any], ...],
        normalized_isin: str,
        normalized_series: str,
        normalized_issuer: str,
    ) -> tuple[dict[str, Any] | None, bool]:
        if normalized_isin:
            candidates = [
                position
                for position in positions
                if cls._normalize_key(position.get("isin")) == normalized_isin
            ]
            selected = cls._select_price_candidate(candidates)
            if selected is not None:
                return selected, False
            if candidates:
                return None, True

        if normalized_series:
            series_candidates = [
                position
                for position in positions
                if cls._normalize_key(position.get("series")) == normalized_series
            ]
            if series_candidates and normalized_issuer:
                issuer_candidates = [
                    position
                    for position in series_candidates
                    if cls._normalize_key(position.get("issuer")) == normalized_issuer
                ]
                selected = cls._select_price_candidate(issuer_candidates)
                if selected is not None:
                    return selected, False
                if issuer_candidates:
                    return None, True
            selected = cls._select_price_candidate(series_candidates)
            if selected is not None:
                return selected, False
            if series_candidates:
                return None, True
        return None, False

    @classmethod
    def _select_price_candidate(
        cls,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        valid: list[tuple[dict[str, Any], Decimal]] = []
        for candidate in candidates:
            price = cls._market_price(candidate)
            if price is not None and price > 0:
                valid.append((candidate, price))
        if not valid:
            return None
        if len({price for _, price in valid}) != 1:
            return None
        return valid[0][0]

    @classmethod
    def _market_price(cls, position: dict[str, Any]) -> Decimal | None:
        value = position.get("market_price_percentage")
        if value is None:
            source_values = position.get("source_values") or {}
            if isinstance(source_values, dict):
                value = source_values.get("porcentaje valor mercado")
        if value is None:
            return None
        try:
            price = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            return None
        return price if price > 0 else None

    @classmethod
    def _prefer_candidate(
        cls,
        *,
        current: Path,
        challenger: Path,
        valuation_date: date,
    ) -> Path:
        exact_name = valuation_date.strftime("%d-%m-%Y")
        current_exact = current.stem.casefold() == exact_name.casefold()
        challenger_exact = challenger.stem.casefold() == exact_name.casefold()
        if current_exact != challenger_exact:
            return challenger if challenger_exact else current
        try:
            return (
                challenger
                if challenger.stat().st_mtime_ns > current.stat().st_mtime_ns
                else current
            )
        except OSError:
            return min((current, challenger), key=lambda path: str(path).casefold())

    @staticmethod
    def _normalize_key(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]", "", ascii_text.casefold())
