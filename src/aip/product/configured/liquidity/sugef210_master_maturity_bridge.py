"""Evidenced principal maturities from the real institutional investment Master.

Requires original-cell principal, maturity and currency evidence. Does not
project coupons, sell investments, use market valuation as principal, or
treat unfunded/illiquid investments as day-zero cash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any, Iterable

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)


@dataclass(frozen=True, slots=True)
class MasterPrincipalExclusion:
    row: str
    reason: str
    currency_original: str


@dataclass(frozen=True, slots=True)
class MasterPrincipalEvidence:
    cutoff: date
    master_sha256: str
    positions_read: int
    flows: tuple[LiquidityProjectionFlow, ...]
    excluded: tuple[MasterPrincipalExclusion, ...]
    principal_by_currency: tuple[tuple[str, Decimal], ...]
    status: str = "MASTER_PRINCIPAL_ONLY_PARTIAL_LIQUIDITY_EVIDENCE"

    @property
    def complete_investment_cashflow_coverage(self) -> bool:
        """Principal schedule alone never proves coupon or realizable-cash coverage."""
        return False


def _currency(raw: str) -> str | None:
    code = raw.strip().upper()
    if code in {"CRC", "COLON", "COLONES"}:
        return "CRC"
    if code in {"USD", "US$", "$", "DOLAR", "DÓLAR", "DOLARES", "DÓLARES"}:
        return "USD"
    return None


def _normalized_header(header: str) -> str:
    """Match normalized source_values keys produced by the institutional reader."""
    cleaned = header.replace("\ufeff", "").replace("\u00a0", " ").replace("_", " ")
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\u2060]", "", cleaned)
    ascii_text = (
        unicodedata.normalize("NFKD", cleaned.strip().lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"\\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text)).strip()


def _principal(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        amount = Decimal(str(raw).strip())
    except (ValueError, InvalidOperation):
        return None
    return amount if amount.is_finite() and amount > 0 else None


def build_master_principal_evidence(
    *,
    cutoff: date,
    master_sha256: str,
    positions: Iterable[dict[str, Any]],
    principal_source_header: str | None,
    maturity_source_header: str | None,
) -> MasterPrincipalEvidence:
    """No cashflow event is emitted for unverified dates, amounts or FX codes."""
    if len(master_sha256) != 64 or any(c not in "0123456789abcdef" for c in master_sha256.lower()):
        raise ValueError("Master source SHA-256 is mandatory")
    rows = tuple(positions)
    events: list[LiquidityProjectionFlow] = []
    excluded: list[MasterPrincipalExclusion] = []
    totals = {"CRC": Decimal(0), "USD": Decimal(0)}
    used_refs: set[str] = set()

    for ordinal, position in enumerate(rows, start=1):
        raw_row = str(position.get("source_row") or ordinal)
        source_values = position.get("source_values")
        native = (
            {_normalized_header(str(key)): value for key, value in source_values.items()}
            if isinstance(source_values, dict)
            else {}
        )
        original_currency = str(position.get("source_currency") or "")
        currency = _currency(original_currency)
        maturity = position.get("maturity_date")
        raw_amount = (
            native.get(_normalized_header(principal_source_header))
            if principal_source_header
            else None
        )
        amount = _principal(raw_amount)
        has_date = bool(
            maturity_source_header and native.get(_normalized_header(maturity_source_header))
        )
        reason = ""
        if currency is None:
            reason = "CURRENCY_NOT_CERTIFIED"
        elif not principal_source_header or amount is None:
            reason = "PRINCIPAL_ORIGINAL_CELL_UNVERIFIED"
        elif not has_date or not isinstance(maturity, date):
            reason = "MATURITY_ORIGINAL_CELL_UNVERIFIED"
        elif maturity <= cutoff:
            reason = "MATURED_OR_NON_FUTURE_POSITION"
        if reason:
            excluded.append(MasterPrincipalExclusion(raw_row, reason, original_currency))
            continue

        assert currency is not None
        assert amount is not None
        assert isinstance(maturity, date)
        reference = f"MASTER:{master_sha256}:{raw_row}:PRINCIPAL"
        if reference in used_refs:
            raise ValueError("Duplicate investment Master source row")
        used_refs.add(reference)
        events.append(
            LiquidityProjectionFlow(
                reference=reference,
                source=f"INSTITUTIONAL_MASTER_SHA256:{master_sha256}:ROW:{raw_row}",
                currency=currency,
                payment_date=maturity,
                amount=amount,
                side=LiquidityFlowSide.INFLOW,
                area=LiquidityBalanceArea.ASSET,
                evidence=LiquidityEvidence.CONTRACTUAL,
            )
        )
        totals[currency] += amount

    return MasterPrincipalEvidence(
        cutoff=cutoff,
        master_sha256=master_sha256,
        positions_read=len(rows),
        flows=tuple(events),
        excluded=tuple(excluded),
        principal_by_currency=tuple(sorted(totals.items())),
    )
