"""Read-only, record-level reconciliation of CONFÍA XML investments with Master.

An unmatched identifier is NOT proof of an investment outside the Master;
a matching ISIN is NOT proof of a duplicate accounting position. Neither
result licenses cash or HQLA recognition without an independent approval.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader


@dataclass(frozen=True, slots=True)
class InvestmentCurrentAccountPolicy:
    """Explicitly approved accounting codes; never infer an on-demand account."""

    approved_account_codes: frozenset[str]
    approval_reference: str
    status: str = "CLASSIFICATION_ONLY_NOT_AVAILABLE_CASH"

    def __post_init__(self) -> None:
        if self.approved_account_codes and not self.approval_reference.strip():
            raise ValueError("Investment current-account classification requires approval")
        if any(not code.strip() for code in self.approved_account_codes):
            raise ValueError("Blank account code is forbidden")


@dataclass(frozen=True, slots=True)
class InvestmentXMLRecordEvidence:
    """Original source references, without inferred availability or FX conversion."""

    source_reference: str
    raw_record_id: str
    record_ordinal: int
    action: str
    account_code: str
    currency_source_code: str
    raw_principal: str
    principal: Decimal | None
    instrument_id: str
    instrument_classification_original: str
    maturity_original: str
    isin: str
    series: str
    classification: str
    master_reconciliation: str
    withdrawable_amount: None = None


@dataclass(frozen=True, slots=True)
class InvestmentXMLAccountGroup:
    account_code: str
    currency_source_code: str
    record_count: int
    principal: Decimal
    classification: str
    master_identifier_matches: int
    unverified_master_overlap: int
    records_without_maturity: int = 0
    classification_five_count: int = 0


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
    records: tuple[InvestmentXMLRecordEvidence, ...] = ()
    repeated_record_ids: int = 0
    status: str = "ACCOUNT_LEVEL_EVIDENCE_ONLY_NO_AVAILABLE_CASH"

    @property
    def cash_available_today(self) -> None:
        """No cash recognition is authorized by inventory or identifier matching."""
        return None


def _amount(value: str) -> Decimal | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def audit_investment_current_accounts(
    *,
    reader: XMLConfiaMonthlySourceReader,
    cutoff: date,
    policy: InvestmentCurrentAccountPolicy,
    master_isins: frozenset[str] = frozenset(),
    master_series: frozenset[str] = frozenset(),
    master_loaded: bool = False,
) -> InvestmentXMLCurrentAccountAudit:
    """Audit all XML records and segregate overlap evidence from bookable funds."""
    source = reader.resolve_source(key="INVESTMENT", cutoff_date=cutoff)
    digest = reader.sha256(source.path)
    known_isins = {identifier.strip().upper() for identifier in master_isins}
    known_series = {identifier.strip().upper() for identifier in master_series}
    master_has_evidence = master_loaded or bool(known_isins or known_series)
    groups: dict[tuple[str, str], dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "records": 0,
            "principal": Decimal(0),
            "matched": 0,
            "uncertain": 0,
            "no_maturity": 0,
            "class_five": 0,
        }
    )
    details: list[InvestmentXMLRecordEvidence] = []
    seen_record_ids: set[str] = set()
    duplicated_ids = 0
    malformed = 0
    missing_accounts = 0

    for ordinal, record in enumerate(reader.iter_records(source), start=1):
        values = record.values
        account = (values.get("CuentaContablePrincipal") or "").strip()
        currency = (values.get("TipoMonedaValorFacial") or "").strip().upper()
        raw_principal = (values.get("SaldoPrincipal") or "").strip()
        principal = _amount(raw_principal)
        isin_original = (values.get("CodISIN") or "").strip().upper()
        # Actual CONFÍA XML uses "NO" to mean absence of an ISIN.
        isin = "" if isin_original in {"NO", "N/A", "NA", "0", "SIN ISIN"} else isin_original
        instrument_class = (values.get("ClasificacionInstrumento") or "").strip()
        maturity_original = (values.get("FechaVencimiento") or "").strip()
        series = (values.get("SerieInstrumento") or "").strip().upper()
        instrument_id = (values.get("IdInstrumento") or "").strip()
        raw_id = record.record_id.strip()
        if raw_id and raw_id in seen_record_ids:
            duplicated_ids += 1
        if raw_id:
            seen_record_ids.add(raw_id)
        if not account:
            missing_accounts += 1
        if principal is None:
            malformed += 1
        match_isin = bool(isin and isin in known_isins)
        match_series = bool(series and series in known_series)
        if principal is None or not account or not currency:
            reconciliation = "INVALID_XML_FIELDS"
        elif not master_has_evidence:
            reconciliation = "MASTER_NOT_LOADED"
        elif match_isin:
            reconciliation = "POSSIBLE_MASTER_OVERLAP_ISIN"
        elif match_series:
            reconciliation = "POSSIBLE_MASTER_OVERLAP_SERIES"
        elif isin or series or instrument_id:
            reconciliation = "UNMATCHED_ID_NOT_PROOF_OF_NEW_BALANCE"
        else:
            reconciliation = "NO_IDENTIFIER_UNRESOLVED"
        classification = (
            "APPROVED_CURRENT_ACCOUNT_CANDIDATE"
            if account in policy.approved_account_codes
            else "NOT_APPROVED_FOR_CURRENT_ACCOUNT"
        )
        group = groups[(account or "(SIN CUENTA)", currency or "(SIN MONEDA)")]
        group["records"] += 1
        if principal is not None:
            group["principal"] += principal
        if not maturity_original:
            group["no_maturity"] += 1
        if instrument_class == "5":
            group["class_five"] += 1
        if match_isin:
            group["matched"] += 1
        else:
            group["uncertain"] += 1
        details.append(
            InvestmentXMLRecordEvidence(
                source_reference=(
                    f"{source.header.id_entidad}:{source.header.periodo.isoformat()}:"
                    f"INVESTMENT:ROW-{ordinal:08d}"
                ),
                raw_record_id=raw_id,
                record_ordinal=ordinal,
                action=record.action,
                account_code=account,
                currency_source_code=currency,
                raw_principal=raw_principal,
                principal=principal,
                instrument_id=instrument_id,
                instrument_classification_original=instrument_class,
                maturity_original=maturity_original,
                isin=isin,
                series=series,
                classification=classification,
                master_reconciliation=reconciliation,
            )
        )

    account_groups = tuple(
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
            records_without_maturity=int(stats["no_maturity"]),
            classification_five_count=int(stats["class_five"]),
        )
        for (account, currency), stats in sorted(groups.items())
    )
    return InvestmentXMLCurrentAccountAudit(
        cutoff=cutoff,
        xml_month=source.header.periodo,
        xml_sha256=digest,
        xml_filename=source.path.name,
        entity_id=source.header.id_entidad,
        records_read=len(details),
        groups=account_groups,
        invalid_source_principal=malformed,
        missing_account_codes=missing_accounts,
        records=tuple(details),
        repeated_record_ids=duplicated_ids,
    )
