from __future__ import annotations

from datetime import date
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.models import FinancialStatementLine, FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_api_client import SUGEFApiReadResult
from aip.product.configured.readers.sugef_official_financial_api_client import (
    SUGEFOfficialFinancialApiClient,
)


class SUGEFCompletePeerFinancialApiClient(SUGEFOfficialFinancialApiClient):
    """Official SUGEF client with exhaustive, selective peer recovery.

    The bulk SFN queries remain the primary source. When the public API omits
    part of the history required by 08ME14-01 for one or more peers, this client
    directly re-queries only the missing methodology accounts for every affected
    entity. It also supplements the current peer snapshot with the same total
    liabilities account observed in the primary entity's authoritative balance.
    No liability account is hard-coded or derived from accounting identities.
    """

    _LIABILITY_ACCOUNT_TERMS = ("TOTAL PASIVO", "PASIVO TOTAL")

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)

    def read(self, cutoff_date: date) -> SUGEFApiReadResult:
        result = super().read(cutoff_date)
        return self._supplement_peer_liabilities(result)

    def _supplement_peer_liabilities(
        self,
        result: SUGEFApiReadResult,
    ) -> SUGEFApiReadResult:
        """Load peer liabilities from the source-native account used by the primary entity."""

        lines = list(result.lines)
        diagnostics = list(result.diagnostics)
        endpoints = set(result.endpoints)
        effective_cutoff = self._primary_statement_cutoff(lines)
        if effective_cutoff is None or not self._config.api_entity_codes:
            return result

        primary = self._config.api_entity_codes[0]
        primary_balance = tuple(
            line
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_date == effective_cutoff
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
        )
        liability_account = self._resolve_liability_account_code(primary_balance)
        if liability_account is None:
            diagnostics.append(
                "No fue posible resolver en el Balance oficial la cuenta IASEF de Pasivo total; "
                "la comparativa conserva N/D sin fabricar valores."
            )
            return SUGEFApiReadResult(
                lines=result.lines,
                endpoints=result.endpoints,
                diagnostics=tuple(diagnostics),
            )

        period = date(effective_cutoff.year, effective_cutoff.month, 1).strftime("%Y%m%d")
        try:
            peer_lines, endpoint = self._read_filtered_report(
                "",
                period,
                *self._BALANCE_REPORT,
                liability_account,
            )
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            diagnostics.append(
                "Pasivos comparativos SFN no disponibles desde la consulta oficial filtrada "
                f"({type(exc).__name__}); la comparativa conserva N/D."
            )
            return SUGEFApiReadResult(
                lines=result.lines,
                endpoints=result.endpoints,
                diagnostics=tuple(diagnostics),
            )

        lines.extend(peer_lines)
        lines = self._deduplicate(lines)
        lines = self._clip_to_primary_statement_cutoff(lines)
        endpoints.add(endpoint)
        peer_count = len(
            {
                line.entity.entity_id
                for line in lines
                if line.statement_date == effective_cutoff
                and line.statement_type is FinancialStatementType.BALANCE_SHEET
                and line.account_code.removesuffix(".0") == liability_account
            }
        )
        diagnostics.append(
            "Pasivos comparativos SFN consultados con la misma cuenta IASEF detectada en "
            "el Balance oficial de la entidad principal: "
            f"{liability_account}; {peer_count} entidad(es) con dato en el corte."
        )
        return SUGEFApiReadResult(
            lines=tuple(lines),
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

    @classmethod
    def _resolve_liability_account_code(
        cls,
        balance_lines: tuple[FinancialStatementLine, ...],
    ) -> str | None:
        """Resolve total liabilities from the primary entity's authoritative full balance."""

        candidates: list[tuple[int, int, str, FinancialStatementLine]] = []
        for line in balance_lines:
            if line.statement_type is not FinancialStatementType.BALANCE_SHEET:
                continue
            normalized = cls._normalize_account_name(line.account_name)
            for term in cls._LIABILITY_ACCOUNT_TERMS:
                if normalized == term:
                    candidates.append((0, len(normalized), line.account_code, line))
                elif term in normalized:
                    candidates.append((1, len(normalized), line.account_code, line))
        if not candidates:
            return None
        selected = min(candidates, key=lambda item: (item[0], item[1], item[2]))[3]
        account_code = selected.account_code.strip().removesuffix(".0")
        return account_code or None

    def _missing_peer_history(
        self,
        lines: list[FinancialStatementLine],
        cutoff_date: date,
    ) -> tuple[str, ...]:
        """Detect incomplete peers from every financial report, not indicators only."""

        primary_codes = set(self._config.api_entity_codes)
        peer_codes = sorted(
            {
                line.entity.entity_id
                for line in lines
                if line.statement_date == cutoff_date
                and line.statement_type
                in {
                    FinancialStatementType.BALANCE_SHEET,
                    FinancialStatementType.INCOME_STATEMENT,
                    FinancialStatementType.INDICATORS,
                }
                and line.entity.entity_id not in primary_codes
            }
        )
        return tuple(
            code
            for code in peer_codes
            if not self._has_methodology_history(lines, code, cutoff_date)
        )

    def _recover_incomplete_peer_history(
        self,
        cutoff_date: date,
        lines: list[FinancialStatementLine],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> None:
        missing = self._missing_peer_history(lines, cutoff_date)
        if not missing:
            return

        jobs = self._missing_methodology_history_jobs(
            entity_codes=missing,
            lines=lines,
            cutoff_date=cutoff_date,
        )
        diagnostics.append(
            "Recuperación selectiva de historia 08ME14-01 activada para "
            f"{len(missing)} entidad(es) incompleta(s): {len(jobs)} consulta(s) de cuenta "
            "pendiente(s), con concurrencia máxima de 2."
        )
        self._execute_filtered_jobs(jobs, lines, endpoints, diagnostics)

        recovered = tuple(
            code for code in missing if self._has_methodology_history(lines, code, cutoff_date)
        )
        recovered_set = set(recovered)
        remaining = tuple(code for code in missing if code not in recovered_set)
        diagnostics.append(
            "Recuperación directa y filtrada de historia SUGEF para comparables 08ME14-01: "
            f"{len(recovered)}/{len(missing)} entidades con historia completa tras la recuperación."
        )
        if remaining:
            diagnostics.append(
                "Entidades que permanecen con historia 08ME14-01 incompleta después de consultar "
                "directamente SUGEF: " + ", ".join(remaining) + "."
            )

    def _missing_methodology_history_jobs(
        self,
        *,
        entity_codes: tuple[str, ...],
        lines: list[FinancialStatementLine],
        cutoff_date: date,
    ) -> list[tuple[str, str, str, str, FinancialStatementType, str]]:
        """Build only account queries whose required history is incomplete."""

        balance_period = self._period_range(
            cutoff_date,
            lookback_months=self._AVERAGE_LOOKBACK_MONTHS,
        )
        income_period = self._result_periods(cutoff_date)
        required_income_dates = {
            cutoff_date,
            self._month_end_date(cutoff_date.year - 1, cutoff_date.month),
            self._month_end_date(cutoff_date.year - 1, 12),
        }
        jobs: list[tuple[str, str, str, str, FinancialStatementType, str]] = []

        for entity_code in entity_codes:
            balance_dates = self._account_dates(
                lines,
                entity_code=entity_code,
                statement_type=FinancialStatementType.BALANCE_SHEET,
                account_codes=self._METHODOLOGY_BALANCE_ACCOUNTS,
                cutoff_date=cutoff_date,
            )
            income_dates = self._account_dates(
                lines,
                entity_code=entity_code,
                statement_type=FinancialStatementType.INCOME_STATEMENT,
                account_codes=self._METHODOLOGY_INCOME_ACCOUNTS,
                cutoff_date=cutoff_date,
            )

            for account_code in self._METHODOLOGY_BALANCE_ACCOUNTS:
                dates = balance_dates[account_code]
                if cutoff_date not in dates or len(dates) < self._AVERAGE_LOOKBACK_MONTHS + 1:
                    jobs.append(
                        (
                            entity_code,
                            balance_period,
                            *self._BALANCE_REPORT,
                            account_code,
                        )
                    )

            for account_code in self._METHODOLOGY_INCOME_ACCOUNTS:
                if not required_income_dates.issubset(income_dates[account_code]):
                    jobs.append(
                        (
                            entity_code,
                            income_period,
                            *self._INCOME_REPORT,
                            account_code,
                        )
                    )

        return jobs

    @staticmethod
    def _account_dates(
        lines: list[FinancialStatementLine],
        *,
        entity_code: str,
        statement_type: FinancialStatementType,
        account_codes: tuple[str, ...],
        cutoff_date: date,
    ) -> dict[str, set[date]]:
        dates_by_account: dict[str, set[date]] = {account: set() for account in account_codes}
        for line in lines:
            if (
                line.entity.entity_id != entity_code
                or line.statement_type is not statement_type
                or line.statement_date > cutoff_date
            ):
                continue
            account = line.account_code.removesuffix(".0")
            if account in dates_by_account:
                dates_by_account[account].add(line.statement_date)
        return dates_by_account
