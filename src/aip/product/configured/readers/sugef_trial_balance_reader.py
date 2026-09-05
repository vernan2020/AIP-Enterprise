from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient


@dataclass(frozen=True, slots=True)
class SUGEFTrialBalanceLine:
    sector_code: str
    sector_name: str
    entity_code: str
    entity_name: str
    statement_date: date
    account_code: str
    catalog_type_code: str
    account_name: str
    account_level: Decimal | None
    ending_balance: Decimal | None
    endpoint: str
    source_row: int


@dataclass(frozen=True, slots=True)
class SUGEFTrialBalanceReadResult:
    lines: tuple[SUGEFTrialBalanceLine, ...]
    endpoints: tuple[str, ...]
    diagnostics: tuple[str, ...]


class SUGEFTrialBalanceReader:
    """Lee la Balanza de Comprobación oficial SUGEF sin imputar saldos faltantes."""

    _REPORT = "ReporteBalanzaComprobacionEntidad"

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFPublicApiClient | None = None,
    ) -> None:
        self._config = config
        self._api = api_client or SUGEFPublicApiClient(config)

    def read(
        self,
        cutoff_date: date,
        *,
        entity_codes: tuple[str, ...] | None = None,
        include_all_entities: bool = False,
        account_code: str = "",
    ) -> SUGEFTrialBalanceReadResult:
        period = date(cutoff_date.year, cutoff_date.month, 1).strftime("%Y%m%d")
        requested = entity_codes if entity_codes is not None else self._config.api_entity_codes
        scopes = list(requested)
        if include_all_entities:
            scopes.append("")
        scopes = list(dict.fromkeys(scopes))

        lines: list[SUGEFTrialBalanceLine] = []
        diagnostics: list[str] = []
        endpoints: set[str] = set()
        direct_entity_codes = {code for code in requested if code}

        for entity_code in scopes:
            try:
                response = self._api.read_financial_entity_report(
                    self._REPORT,
                    entity_code=entity_code,
                    periods=period,
                    account_code=account_code,
                )
                endpoints.add(response.endpoint)
                normalized = self._normalize_rows(response.rows, response.endpoint)
                if entity_code == "" and direct_entity_codes:
                    normalized = tuple(
                        line for line in normalized if line.entity_code not in direct_entity_codes
                    )
                lines.extend(normalized)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                scope = entity_code or "todas las entidades"
                diagnostics.append(
                    f"SUGEF API Balanza de Comprobación ({scope}): " f"{type(exc).__name__}: {exc}"
                )

        if lines:
            null_balances = sum(line.ending_balance is None for line in lines)
            diagnostics.append(
                f"Balanza de Comprobación SUGEF: {len(lines)} filas normalizadas para "
                f"{cutoff_date:%m/%Y}."
            )
            if null_balances:
                diagnostics.append(
                    f"Balanza de Comprobación SUGEF: {null_balances} saldos publicados como "
                    "nulos se conservan N/D; no se transforman en cero."
                )
        elif not diagnostics:
            diagnostics.append(
                f"Balanza de Comprobación SUGEF: sin filas para {cutoff_date:%m/%Y}."
            )
        return SUGEFTrialBalanceReadResult(
            lines=tuple(lines),
            endpoints=tuple(sorted(endpoints)),
            diagnostics=tuple(diagnostics),
        )

    @classmethod
    def _normalize_rows(
        cls,
        rows: tuple[Mapping[str, Any], ...],
        endpoint: str,
    ) -> tuple[SUGEFTrialBalanceLine, ...]:
        result: list[SUGEFTrialBalanceLine] = []
        for row_number, row in enumerate(rows, start=1):
            entity_code = cls._identifier(row.get("codigoEntidad"))
            entity_name = cls._text(row.get("nombreEntidad"))
            statement_date = cls._month_end(row.get("periodo"))
            account_code = cls._identifier(row.get("cuentaCatalogoSugef"))
            catalog_type_code = cls._identifier(row.get("codigoTipoCatalogo"))
            account_name = cls._text(row.get("nombreCuenta"))
            if (
                not entity_code
                or not entity_name
                or statement_date is None
                or not account_code
                or not catalog_type_code
                or not account_name
            ):
                continue
            result.append(
                SUGEFTrialBalanceLine(
                    sector_code=cls._identifier(row.get("codigoSector")),
                    sector_name=cls._text(row.get("descripcionSector")),
                    entity_code=entity_code,
                    entity_name=entity_name,
                    statement_date=statement_date,
                    account_code=account_code,
                    catalog_type_code=catalog_type_code,
                    account_name=account_name,
                    account_level=cls._decimal(row.get("nivelCuenta")),
                    ending_balance=cls._decimal(row.get("saldoFinal")),
                    endpoint=endpoint,
                    source_row=row_number,
                )
            )
        return tuple(result)

    @staticmethod
    def _month_end(value: Any) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None
        return date(parsed.year, parsed.month, monthrange(parsed.year, parsed.month)[1])

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def _identifier(cls, value: Any) -> str:
        if value is None or isinstance(value, bool):
            return ""
        if isinstance(value, str):
            text = value.strip()
            return text[:-2] if text.endswith(".0") and text[:-2].isdigit() else text
        decimal = cls._decimal(value)
        if decimal is None or decimal != decimal.to_integral_value():
            return cls._text(value)
        return str(int(decimal))

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()
