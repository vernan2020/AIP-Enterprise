from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.product.configured.irrbb.regulatory_financial_xml import RegulatoryXMLPairResult

# Official SICVECA Class 22 Financial v202007: Rango_Brecha 1..6.
REGULATORY_BRECHA_BUCKETS: tuple[tuple[str, str], ...] = (
    ("1", "0–30 días"),
    ("2", "31–90 días"),
    ("3", "91–180 días"),
    ("4", "181–360 días"),
    ("5", "361–720 días"),
    ("6", "Más de 720 días"),
)
# Regulatory mother rows: assets 22310 = 22110 (MN) + 22210 (ME);
# liabilities 22320 = 22120 (MN) + 22220 (ME).
REGULATORY_GAP_ACCOUNTS = ("22110", "22210", "22310", "22120", "22220", "22320")


@dataclass(frozen=True, slots=True)
class RegulatoryGapBucket:
    bucket_code: str
    bucket_label: str
    assets_crc: Decimal
    liabilities_crc: Decimal
    gap_crc: Decimal
    cumulative_gap_crc: Decimal


@dataclass(frozen=True, slots=True)
class RegulatoryGapResult:
    """Independent six-band regulatory GAP; never the 19-band or ΔEVE output."""

    status: str
    rows: tuple[RegulatoryGapBucket, ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "RECONCILED"


def build_regulatory_gap(snapshot: RegulatoryXMLPairResult) -> RegulatoryGapResult:
    """Derive only when six bands and official MN+ME controls reconcile.

    Missing source rows must not be replaced by inferred zeros. Inputs are
    source-coded CRC-equivalent balances, not contractual valuation cashflows.
    """
    if not snapshot.is_valid:
        return RegulatoryGapResult(
            "BLOCKED", issues=("Los XML del corte no están validados estructuralmente.",)
        )
    brechas = next((item for item in snapshot.files if item.key == "BRECHAS"), None)
    if brechas is None or not brechas.is_valid:
        return RegulatoryGapResult("BLOCKED", issues=("XML Brechas no disponible.",))

    source = {(row.account_code, row.bucket_code): row.amount for row in brechas.rows}
    issues: list[str] = []
    derived: list[RegulatoryGapBucket] = []
    cumulative = Decimal("0")
    for band, label in REGULATORY_BRECHA_BUCKETS:
        missing = [account for account in REGULATORY_GAP_ACCOUNTS if (account, band) not in source]
        if missing:
            issues.append(f"Banda {band}: faltan cuentas oficiales: {', '.join(missing)}.")
            continue
        assets_mn, assets_me, assets = (
            source[("22110", band)],
            source[("22210", band)],
            source[("22310", band)],
        )
        liabilities_mn, liabilities_me, liabilities = (
            source[("22120", band)],
            source[("22220", band)],
            source[("22320", band)],
        )
        if assets_mn + assets_me != assets:
            issues.append(f"Banda {band}: activos MN+ME no concilian con 22310.")
        if liabilities_mn + liabilities_me != liabilities:
            issues.append(f"Banda {band}: pasivos MN+ME no concilian con 22320.")
        delta = assets - liabilities
        cumulative += delta
        derived.append(RegulatoryGapBucket(band, label, assets, liabilities, delta, cumulative))

    if issues or len(derived) != len(REGULATORY_BRECHA_BUCKETS):
        return RegulatoryGapResult("BLOCKED", issues=tuple(issues))
    return RegulatoryGapResult("RECONCILED", rows=tuple(derived))
