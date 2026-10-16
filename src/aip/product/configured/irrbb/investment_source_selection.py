"""Governed investment source selection for institutional RTILB.

The institutional portfolio master is the authoritative investment position
source. SICVECA investment XML is reconciliation-only and must never be
combined with the master as a second position feed.
"""

from __future__ import annotations

from dataclasses import dataclass

from aip.product.configured.irrbb.investment_master_batch_bridge import (
    InvestmentMasterBatchBridgeResult,
)


@dataclass(frozen=True, slots=True)
class RTILBInvestmentSourceDecision:
    source: str
    reconciliation_source: str
    status: str
    canonical_positions: int
    mapping_failures: int
    diagnostics: tuple[str, ...]


def select_investment_source(
    master: InvestmentMasterBatchBridgeResult,
) -> RTILBInvestmentSourceDecision:
    """Use only certified master positions; fail closed without XML substitution."""
    certification_status = str(master.certification.status.value)
    snapshot_status = str(master.snapshot.status.value)
    count = len(master.snapshot.position_records)
    failures = len(master.snapshot.mapping_failures)
    # The bridge's source-certification gate owns authority to release positions.
    ready = certification_status == "READY" and snapshot_status == "AVAILABLE"
    if not ready:
        return RTILBInvestmentSourceDecision(
            source="INSTITUTIONAL_PORTFOLIO_MASTER",
            reconciliation_source="Crediticio_InversionesActivas.xml",
            status="BLOCKED",
            canonical_positions=0,
            mapping_failures=failures,
            diagnostics=(
                f"Master certification: {certification_status}",
                f"Source snapshot: {snapshot_status}",
                "Investment XML is reconciliation-only; no fallback positions are generated.",
            ),
        )
    return RTILBInvestmentSourceDecision(
        source="INSTITUTIONAL_PORTFOLIO_MASTER",
        reconciliation_source="Crediticio_InversionesActivas.xml",
        status="READY",
        canonical_positions=count,
        mapping_failures=failures,
        diagnostics=(
            "Investment positions originate only from the certified master.",
        ),
    )
