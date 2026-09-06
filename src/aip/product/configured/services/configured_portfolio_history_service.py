from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.configuration.institutional_paths import resolve_institutional_path
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.protocols import SourceHealthProvider
from aip.product.configured.services.configured_portfolio_dashboard_analytics_service import (
    ConfiguredPortfolioDashboardAnalyticsService,
)
from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.demo.configuration.demo_config import DemoConfig


HistorySampling = Literal["monthly", "daily"]


@dataclass(frozen=True, slots=True)
class PortfolioKPIHistoryPoint:
    """Certified KPI snapshot calculated from one institutional portfolio cut."""

    valuation_date: date
    market_value_crc: Decimal
    weighted_yield_percent: Decimal
    modified_duration: Decimal | None
    hqla_percent: Decimal
    dv01_crc: Decimal | None
    hhi: Decimal
    data_quality_status: str
    master_source_date: date | None


@dataclass(frozen=True, slots=True)
class PortfolioKPIHistoryResult:
    points: tuple[PortfolioKPIHistoryPoint, ...]
    status: str
    warnings: tuple[str, ...] = ()


class ConfiguredPortfolioHistoryService:
    """Build historical portfolio KPI series without mutating the active valuation session."""

    _SUPPORTED_EXTENSIONS = {".xls", ".xlsx", ".txt"}
    _REJECT_TOKENS = {"prueba", "revision", "revisado", "copia", "respaldo", "canje"}
    _DATE_PATTERN = re.compile(
        r"(?P<day>\d{1,2})[-.]?(?P<month>\d{1,2})[-.]?(?P<year>\d{4})"
    )
    _COMPACT_DATE_PATTERN = re.compile(
        r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
    )

    def __init__(
        self,
        config: DemoConfig,
        source_config: ConfiguredSourceConfig,
        health_provider: SourceHealthProvider | None = None,
    ) -> None:
        self._config = config
        self._source_config = source_config
        self._health_provider = health_provider
        self._cache: dict[
            tuple[date | None, date | None, HistorySampling, int],
            PortfolioKPIHistoryResult,
        ] = {}
        self._cache_lock = RLock()

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None or value == "":
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _optional_decimal(value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _parse_iso_date(value: object) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    def load(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        sampling: HistorySampling = "monthly",
        max_points: int = 96,
    ) -> PortfolioKPIHistoryResult:
        """Calculate history from exact institutional cuts, never synthetic interpolation."""

        if sampling not in {"monthly", "daily"}:
            raise ValueError("sampling must be 'monthly' or 'daily'")
        if max_points < 1:
            raise ValueError("max_points must be greater than zero")

        resolved_end = end_date or self._config.data_cutoff_date
        cache_key = (start_date, resolved_end, sampling, max_points)
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        available_dates = self._discover_available_dates(
            start_date=start_date,
            end_date=resolved_end,
        )
        selected_dates = self._sample_dates(available_dates, sampling=sampling)
        if len(selected_dates) > max_points:
            selected_dates = selected_dates[-max_points:]

        if not selected_dates:
            result = PortfolioKPIHistoryResult(
                points=(),
                status="UNAVAILABLE",
                warnings=("No se encontraron cortes históricos institucionales del portafolio.",),
            )
            with self._cache_lock:
                self._cache[cache_key] = result
            return result

        local_context = ValuationDateContext(resolved_end)
        provider = ConfiguredPortfolioProvider(
            self._config,
            self._source_config,
            self._health_provider,
            valuation_date_context=local_context,
        )
        dv01_service = ConfiguredPortfolioDV01Service(provider)

        points: list[PortfolioKPIHistoryPoint] = []
        warnings: list[str] = []
        for valuation_date in selected_dates:
            local_context.set(valuation_date)
            try:
                portfolio = provider.get_portfolio()
            except Exception as exc:
                warnings.append(
                    f"{valuation_date.isoformat()}: no fue posible cargar el corte ({exc})."
                )
                continue

            positions = [
                item for item in portfolio.get("positions", ()) if isinstance(item, dict)
            ]
            master = portfolio.get("portfolio_master")
            master_payload = master if isinstance(master, dict) else {}
            master_status = str(master_payload.get("status") or "").upper()
            if not positions or master_status == "UNAVAILABLE":
                warnings.append(
                    f"{valuation_date.isoformat()}: corte sin posiciones institucionales utilizables."
                )
                continue

            analytics = ConfiguredPortfolioDashboardAnalyticsService.calculate(
                portfolio=portfolio
            )
            dv01_value: Decimal | None
            try:
                dv01_value = dv01_service.calculate(
                    portfolio=portfolio
                ).total_dv01_crc
            except Exception:
                dv01_value = None

            point_date = self._parse_iso_date(portfolio.get("valuation_date")) or valuation_date
            points.append(
                PortfolioKPIHistoryPoint(
                    valuation_date=point_date,
                    market_value_crc=self._decimal(portfolio.get("market_value")),
                    weighted_yield_percent=self._decimal(portfolio.get("weighted_yield")),
                    modified_duration=self._optional_decimal(
                        portfolio.get("modified_duration")
                    ),
                    hqla_percent=self._decimal(portfolio.get("hqla_percent")),
                    dv01_crc=dv01_value,
                    hhi=analytics.hhi,
                    data_quality_status=str(
                        portfolio.get("data_quality_status") or "N/D"
                    ),
                    master_source_date=self._parse_iso_date(
                        master_payload.get("valuation_date")
                    ),
                )
            )

        points.sort(key=lambda item: item.valuation_date)
        status = "HEALTHY"
        if not points:
            status = "UNAVAILABLE"
        elif warnings:
            status = "DEGRADED"

        result = PortfolioKPIHistoryResult(
            points=tuple(points),
            status=status,
            warnings=tuple(warnings),
        )
        with self._cache_lock:
            self._cache[cache_key] = result
        return result

    def _discover_available_dates(
        self,
        *,
        start_date: date | None,
        end_date: date,
    ) -> tuple[date, ...]:
        root = self._resolve_investment_root()
        if root is None or not root.exists():
            return ()

        dates: set[date] = set()
        for year_directory in root.iterdir():
            if not year_directory.is_dir() or not year_directory.name.isdigit():
                continue
            year = int(year_directory.name)
            if year > end_date.year:
                continue
            if start_date is not None and year < start_date.year:
                continue

            master_root = year_directory / "maestro"
            if not master_root.exists() or not master_root.is_dir():
                continue
            for file_path in master_root.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() not in self._SUPPORTED_EXTENSIONS:
                    continue
                normalized = self._normalize(file_path.name)
                if any(token in normalized for token in self._REJECT_TOKENS):
                    continue
                parsed = self._parse_date_from_name(normalized)
                if parsed is None or parsed > end_date:
                    continue
                if start_date is not None and parsed < start_date:
                    continue
                dates.add(parsed)
        return tuple(sorted(dates))

    def _resolve_investment_root(self) -> Path | None:
        configured_root = self._source_config.folder_watch.portfolio_root
        if not configured_root:
            return None
        normalized = resolve_institutional_path(configured_root) or configured_root
        root = Path(normalized)
        if root.name.casefold() == "inversiones":
            return root
        if root.exists() and root.is_dir() and (root / "Inversiones").exists():
            return root / "Inversiones"
        return root / "Inversiones"

    @classmethod
    def _parse_date_from_name(cls, value: str) -> date | None:
        compact = cls._COMPACT_DATE_PATTERN.search(value)
        if compact is not None:
            try:
                return date(
                    int(compact.group("year")),
                    int(compact.group("month")),
                    int(compact.group("day")),
                )
            except ValueError:
                return None
        match = cls._DATE_PATTERN.search(value)
        if match is None:
            return None
        try:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            return None

    @staticmethod
    def _sample_dates(
        values: tuple[date, ...],
        *,
        sampling: HistorySampling,
    ) -> list[date]:
        if sampling == "daily":
            return list(values)
        monthly: dict[tuple[int, int], date] = {}
        for value in values:
            monthly[(value.year, value.month)] = max(
                value,
                monthly.get((value.year, value.month), value),
            )
        return sorted(monthly.values())

    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", value)
        ascii_text = text.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", ascii_text).strip().casefold()
