from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FinancialMetricView:
    code: str
    label: str
    value: str
    change: str
    source_account: str


@dataclass(frozen=True, slots=True)
class FinancialStatementRow:
    statement: str
    account_code: str
    account_name: str
    amount: str
    currency: str
    trace: str


@dataclass(frozen=True, slots=True)
class PeerSummaryRow:
    entity_id: str
    entity_name: str
    category: str
    assets: str
    loans: str
    equity: str
    net_income: str
    roa: str
    roe: str


@dataclass(frozen=True, slots=True)
class FinancialAnalysisViewModel:
    title: str = "ANÁLISIS FINANCIERO"
    subtitle: str = "Estados financieros y comparación de entidades supervisadas por SUGEF"
    status: str = "UNAVAILABLE"
    cutoff_date: str = "-"
    selected_entity_id: str = ""
    selected_entity_name: str = "Sin datos"
    entities: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    metrics: tuple[FinancialMetricView, ...] = field(default_factory=tuple)
    statement_rows: tuple[FinancialStatementRow, ...] = field(default_factory=tuple)
    peer_rows: tuple[PeerSummaryRow, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    source_name: str = "SUGEF"
    source_url: str = "https://www.sugef.fi.cr/reportes/Informacion_Financiera_Contable.aspx"
    source_file_count: int = 0
