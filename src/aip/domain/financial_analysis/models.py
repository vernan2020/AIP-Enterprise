from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class FinancialStatementType(StrEnum):
    BALANCE_SHEET = "BALANCE_SHEET"
    INCOME_STATEMENT = "INCOME_STATEMENT"
    INDICATORS = "INDICATORS"
    TRIAL_BALANCE = "TRIAL_BALANCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SourceTrace:
    source_name: str
    source_url: str
    file_path: str
    sheet_name: str
    row_number: int


@dataclass(frozen=True, slots=True)
class FinancialEntity:
    entity_id: str
    name: str
    category: str = "Sin clasificar"


@dataclass(frozen=True, slots=True)
class FinancialStatementLine:
    entity: FinancialEntity
    statement_date: date
    statement_type: FinancialStatementType
    account_code: str
    account_name: str
    amount: Decimal
    currency: str = "CRC"
    trace: SourceTrace | None = None


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    code: str
    label: str
    value: Decimal | None
    unit: str
    previous_value: Decimal | None = None
    change_percent: Decimal | None = None
    source_account: str | None = None


@dataclass(frozen=True, slots=True)
class EntityFinancialSummary:
    entity: FinancialEntity
    statement_date: date
    assets: Decimal | None = None
    loans: Decimal | None = None
    liabilities: Decimal | None = None
    equity: Decimal | None = None
    net_income: Decimal | None = None
    roa_percent: Decimal | None = None
    roe_percent: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FinancialAnalysisSnapshot:
    status: str
    cutoff_date: date | None
    selected_entity: FinancialEntity | None
    entities: tuple[FinancialEntity, ...] = field(default_factory=tuple)
    available_dates: tuple[date, ...] = field(default_factory=tuple)
    metrics: tuple[FinancialMetric, ...] = field(default_factory=tuple)
    statement_lines: tuple[FinancialStatementLine, ...] = field(default_factory=tuple)
    peer_summaries: tuple[EntityFinancialSummary, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    source_name: str = "SUGEF"
    source_url: str = "https://www.sugef.fi.cr/reportes/Informacion_Financiera_Contable.aspx"
    source_files: tuple[str, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        return self.status == "AVAILABLE" and bool(self.statement_lines)
