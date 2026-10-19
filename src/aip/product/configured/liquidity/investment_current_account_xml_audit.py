"""Read-only XML CONFÍA investment current-account discovery for Liquidity.

No assumption that a security or an investment account is an available-on-demand
balance. Account classification is governed by an explicitly approved list; the
raw XML alone lacks proof of withdrawability or settlement on day zero.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader


@dataclass(frozen=True, slots=True)
class InvestmentCurrentAccountPolicy:
    """Approved account codes only, no wildcard prefixes or inferred liquidity."""

    approved_account_codes: frozenset[str]
    approval_reference: str
    status: str = "CLASSIFICATION_ONLY_NOT_AVAILABLE_CASH"

    def __post_init__(self) -> None:
        if self.approved_account_codes and not self.approval_reference.strip():
            raise ValueError("Investment current-account classification requires approval")
        if any(not code.strip() for code in self.approved_account_codes):
            raise ValueError("Blank account code is forbidden")


@dataclass(frozen=True, slots=True)
class InvestmentXMLAccountGroup:
    account_code: str
    currency_source_code: str
    record_count: int
    principal: Decimal
    classification: str
    master_identifier_matches: int
    unverified_master_overlap: int


@dataclass(frozen=True, slots=True)
class InvestmentXMLCurrentAccountAudit:
    cutoff: date
    xml_month: date
    xml_sha256: str
    xml_filename: str
    entity_id: str
    records_read: int
    groups: tuple[InvestmentXMLAccountGroup, ...]
    invalid_source_principal: int
    missing_account_codes: int
    status: str = "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH"

    @property
    def cash_available_today(self) -> None:
        """Availability must be validated separately, never inferred from XML."""
        return None


def _amount(value: str) -> Decimal | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        d = Decimal(raw)
    except InvalidOperation:
        return None
    return d if d.is_finite() and d >= 0 else None


def audit_investment_current_accounts(
    *,
    reader: XMLConfiaMonthlySourceReader,
    cutoff: date,
    policy: InvestmentCurrentAccountPolicy,
    master_isins: frozenset[str] = frozenset(),
) -> InvestmentXMLCurrentAccountAudit:
    """Account-code inventory and duplicate evidence, not liquidity booking."""
    source = reader.resolve_source(key="INVESTMENT", cutoff_date=cutoff)
    account_groups: dict[tuple[str, str], dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "records": 0,
            "principal": Decimal(0),
            "matched": 0,
            "uncertain": 0,
        }
    )
    malformed = 0
    account_missing = 0
    records = 0
    for record in reader.iter_records(source):
        records += 1
        values = record.values
        account = (values.get("CuentaContablePrincipal") or "").strip()
        currency = (values.get("TipoMonedaValorFacial") or "").strip().upper()
        principal = _amount(values.get("SaldoPrincipal") or "")
        if not account:
            account_missing += 1
        if principal is None:
            malformed += 1
        isin = (values.get("CodISIN") or "").strip().upper()
        item = account_groups[(account or "(SIN CUENTA)", currency or "(SIN MONEDA)")]
        item["records"] += 1
        if principal is not None:
            item["principal"] += principal
        if isin and isin in master_isins:
            item["matched"] += 1
        elif not isin:
            # No verified linkage to Master: never declare it 'not duplicated'.
            item["uncertain"] += 1
    groups = tuple(
        InvestmentXMLAccountGroup(
            account_code=account,
            currency_source_code=currency,
            record_count=int(stats["records"]),
            principal=stats["principal"],
            classification=(
                "APPROVED_CURRENT_ACCOUNT_CANDIDATE"
                if account in policy.approved_account_codes
                else "NOT_APPROVED_FOR_CURRENT_ACCOUNT"
            ),
            master_identifier_matches=int(stats["matched"]),
            unverified_master_overlap=int(stats["uncertain"]),
        )
        for (account, currency), stats in sorted(account_groups.items())
    )
    return InvestmentXMLCurrentAccountAudit(
        cutoff=cutoff, xml_month=source.header.periodo,
        xml_sha256=reader.sha256(source.path),
        xml_filename=source.path.name, entity_id=source.header.id_entidad,
        records_read=records, groups=groups,
        invalid_source_principal=malformed, missing_account_codes=account_missing,
    )
