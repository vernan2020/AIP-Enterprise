from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    PortfolioCapitalEvidenceService,
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_duration_service import PortfolioDurationService
from aip.domain.portfolio.services.portfolio_dv01_service import PortfolioDV01Service
from aip.domain.portfolio.services.portfolio_hqla_service import PortfolioHQLAService
from aip.domain.portfolio.services.portfolio_scenario_evidence_bridge import (
    VerifiedPositionMarketRisk,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
    InstitutionalPortfolioMasterReadResult,
)


@dataclass(frozen=True, slots=True)
class InstitutionalScenarioMarketEvidence:
    """Dated source and auditable sensitivity rows; never regulatory classification."""

    cutoff: date
    master_file: str
    sheet_name: str
    market_risks: tuple[VerifiedPositionMarketRisk, ...]
    total_market_value_crc: Decimal


class InstitutionalMasterScenarioRiskAdapter:
    """Bridge the institutional master reader to existing duration/DV01/HQLA engines.

    This adapter requires native CRC valuation and approved lot-to-row identities.
    It never uses the configured dashboard's market-value fallback, converts
    local-currency market values to CRC, or guesses exposure classes.
    Regulatory capital remains an independently verified input.
    """

    _DATED_FILENAME = re.compile(
        r"(?<!\\d)(?P<day>\\d{1,2})[-_.]?(?P<month>\\d{1,2})[-_.]?(?P<year>\\d{4})(?!\\d)"
    )
    _REQUIRED_NATIVE_COLUMNS = frozenset(
        {"market_value_crc", "currency", "issuer", "isin", "classification", "product_code"}
    )

    @classmethod
    def read_file(
        cls,
        master_file: str | Path,
        capital_positions: Sequence[VerifiedCapitalPosition],
        source_row_by_position: Mapping[str, int],
        *,
        cutoff: date,
    ) -> InstitutionalScenarioMarketEvidence:
        """Use explicit cutoff override only after checking the native filename date."""
        file_name = Path(master_file).stem
        candidates: list[date] = []
        for match in cls._DATED_FILENAME.finditer(file_name):
            try:
                candidates.append(
                    date(
                        int(match.group("year")),
                        int(match.group("month")),
                        int(match.group("day")),
                    )
                )
            except ValueError as exc:
                raise ValueError("Master filename contains an invalid date") from exc
        if len(candidates) != 1:
            raise ValueError("Institutional master filename needs one DD-MM-YYYY cutoff")
        if candidates[0] != cutoff:
            raise ValueError("Institutional master filename cutoff does not match selection")
        reader_result = InstitutionalPortfolioMasterReader().read(
            master_file, valuation_date_override=cutoff
        )
        return cls.adapt(
            reader_result,
            capital_positions,
            source_row_by_position,
            cutoff=cutoff,
        )

    @classmethod
    def adapt(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
        capital_positions: Sequence[VerifiedCapitalPosition],
        source_row_by_position: Mapping[str, int],
        *,
        cutoff: date,
    ) -> InstitutionalScenarioMarketEvidence:
        positions = PortfolioCapitalEvidenceService.validate(capital_positions, cutoff=cutoff)
        if (
            result.valuation_date != cutoff
            or result.source_status != "HEALTHY"
            or result.warnings
            or result.rejected_row_count
            or not result.source_file.strip()
            or not result.sheet_selected.strip()
        ):
            raise ValueError("Institutional master cutoff, completeness or source is unverified")
        missing_columns = cls._REQUIRED_NATIVE_COLUMNS.difference(
            result.detected_column_mapping
        )
        if missing_columns:
            raise ValueError(
                "Native institutional columns missing: " + ", ".join(sorted(missing_columns))
            )
        keys = tuple(position.position_key for position in positions)
        if set(source_row_by_position) != set(keys):
            raise ValueError("Approved row mapping must cover every audited capital lot")
        mapped_rows = tuple(source_row_by_position[key] for key in keys)
        if (
            any(type(row_number) is not int or row_number <= 0 for row_number in mapped_rows)
            or len(set(mapped_rows)) != len(mapped_rows)
        ):
            raise ValueError("Approved physical source row numbers must be unique integers")

        raw = tuple(result.normalized_positions)
        source_rows = tuple(item.get("source_row") for item in raw)
        if (
            len(raw) != len(positions)
            or len(set(source_rows)) != len(source_rows)
            or set(source_rows) != set(mapped_rows)
        ):
            raise ValueError("Every institutional master row must match one approved capital lot")
        by_row = {item["source_row"]: item for item in raw}

        def finite(value: object) -> Decimal:
            if value is None or isinstance(value, bool):
                raise ValueError("Native numeric evidence is unavailable")
            try:
                number = Decimal(str(value))
            except (ValueError, ArithmeticError, TypeError) as exc:
                raise ValueError("Native numeric evidence is invalid") from exc
            if not number.is_finite():
                raise ValueError("Native numeric evidence must be finite")
            return number

        market_risks: list[VerifiedPositionMarketRisk] = []
        for capital, row_number in zip(positions, mapped_rows, strict=True):
            row = by_row[row_number]
            original_currency = str(row.get("source_currency") or "").strip().upper()
            capital_currency = capital.currency.strip().upper()
            if original_currency != capital_currency or original_currency not in {"CRC", "USD"}:
                raise ValueError("Native master currency is missing or does not match capital lot")
            if (
                str(row.get("isin") or "").strip().upper() != capital.isin.strip().upper()
                or str(row.get("issuer") or "").strip().casefold()
                != capital.issuer.strip().casefold()
            ):
                raise ValueError("Native ISIN or issuer does not match approved capital identity")
            if (
                not str(row.get("classification") or "").strip()
                or not str(row.get("product_code") or "").strip()
            ):
                raise ValueError("Native instrument classification and product are required")

            market = finite(row.get("market_value_crc"))
            if market <= 0:
                raise ValueError("Native market value CRC must be positive")

            engine_row = dict(row)
            principal = row.get("principal_balance")
            if principal is not None:
                if "principal_balance" not in result.detected_column_mapping:
                    raise ValueError("Duration principal must originate in a native column")
                engine_row["nominal"] = finite(principal)
            engine_row["market_value_crc"] = market
            duration = PortfolioDurationService.calculate(engine_row, cutoff)
            if (
                duration.modified_duration is None
                or not duration.modified_duration.is_finite()
                or duration.modified_duration < 0
                or not duration.included_in_portfolio_duration
            ):
                raise ValueError("Audited modified duration is not available for every lot")
            engine_row["modified_duration"] = duration.modified_duration
            dv01 = PortfolioDV01Service.calculate(engine_row)
            if dv01.status != "CALCULATED" or dv01.dv01_crc is None:
                raise ValueError("Institutional DV01 cannot be calculated for every lot")
            hqla = PortfolioHQLAService.calculate(engine_row)
            if not hqla.hqla_value_crc.is_finite():
                raise ValueError("HQLA result must be finite")
            source = (
                f"{result.source_file}|{result.sheet_selected}|row:{row_number}"
                f"|cutoff:{cutoff.isoformat()}"
            )
            market_risks.append(
                VerifiedPositionMarketRisk(
                    position_key=capital.position_key,
                    cutoff=cutoff,
                    market_value_crc=market,
                    modified_duration_years=duration.modified_duration,
                    dv01_crc=dv01.dv01_crc,
                    eligible_hqla_value_crc=hqla.hqla_value_crc,
                    market_value_source=(
                        f"{source}|column:{result.detected_column_mapping['market_value_crc']}"
                    ),
                    duration_source=f"{source}|duration:{duration.method}|{duration.source}",
                    dv01_source=f"{source}|dv01:{dv01.method}|{dv01.source}",
                    hqla_source=f"{source}|hqla:{hqla.status}|{hqla.source}",
                )
            )

        return InstitutionalScenarioMarketEvidence(
            cutoff=cutoff,
            master_file=result.source_file,
            sheet_name=result.sheet_selected,
            market_risks=tuple(market_risks),
            total_market_value_crc=sum(
                (row.market_value_crc for row in market_risks), Decimal("0")
            ),
        )
