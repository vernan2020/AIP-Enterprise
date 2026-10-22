"""Independent source-line verification of the binding 08ME14-01 rating.

Checks the source-selected value and P15/P85 cohort arithmetic from the
same-period SUGEF records. This is read-only and never awards or modifies
points. It does not use the spreadsheet's relative-category thresholds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    EntityFinancialRating,
    FinancialStatementLine,
    RatingDirection,
)
from aip.domain.financial_analysis.sugef_ratings import (
    SUGEFOnlyFinancialEntityRatingService,
)


@dataclass(frozen=True, slots=True)
class SourcePercentileAuditRow:
    code: str
    selected_value: Decimal | None
    rated_value: Decimal | None
    observed_peers: int
    rated_peers: int
    observed_p15: Decimal | None
    rated_p15: Decimal | None
    observed_midpoint: Decimal | None
    rated_midpoint: Decimal | None
    observed_p85: Decimal | None
    rated_p85: Decimal | None
    status: str


@dataclass(frozen=True, slots=True)
class SourcePercentileAuditResult:
    status: str
    rows: tuple[SourcePercentileAuditRow, ...]
    discrepancies: tuple[str, ...]


class NormativeSourcePercentileAuditor:
    """Compare AIP's percentiles with independently interpolated source data."""

    @staticmethod
    def _percentile(values: tuple[Decimal, ...], percentile: Decimal) -> Decimal:
        if not values:
            raise ValueError("No percentile can be computed for an empty cohort.")
        ordered = sorted(values)
        rank = (len(ordered) - 1) * percentile
        left = int(rank)
        right = min(left + 1, len(ordered) - 1)
        return ordered[left] * (right - rank) + ordered[right] * (rank - left) if left != right else ordered[left]

    @classmethod
    def audit(
        cls,
        lines: tuple[FinancialStatementLine, ...],
        *,
        entity_id: str,
        rating: EntityFinancialRating,
    ) -> SourcePercentileAuditResult:
        service = SUGEFOnlyFinancialEntityRatingService()
        cutoff = rating.effective_date
        canonical = service._canonical_roa_lines(lines, cutoff_date=cutoff)
        current = (*(
            line for line in lines if line.statement_date == cutoff
        ), *canonical)
        by_entity: dict[str, list[FinancialStatementLine]] = defaultdict(list)
        for line in current:
            by_entity[line.entity.entity_id].append(line)
        ratings = {row.code: row for row in rating.indicators}
        rows: list[SourcePercentileAuditRow] = []
        issues: list[str] = []
        for definition in service.INDICATORS:
            item = ratings.get(definition.code)
            if item is None:
                issues.append(f"Indicador obligatorio ausente: {definition.code}")
                continue
            current_value = service._find_indicator(
                tuple(by_entity.get(entity_id, ())), definition
            )
            expected = current_value.amount if current_value is not None else None
            if definition.direction is RatingDirection.BINARY:
                peers = 0
                p15 = mid = p85 = None
            else:
                values = tuple(
                    source.amount
                    for entity_lines in by_entity.values()
                    if (source := service._find_indicator(tuple(entity_lines), definition))
                    is not None
                )
                peers = len(values)
                if peers >= service.MINIMUM_PEERS and expected is not None:
                    p15 = cls._percentile(values, Decimal("0.15"))
                    p85 = cls._percentile(values, Decimal("0.85"))
                    mid = (p15 + p85) / Decimal("2")
                else:
                    p15 = mid = p85 = None
            differences = []
            if expected != item.value:
                differences.append("valor")
            if peers != item.peer_count:
                differences.append("pares")
            if p15 != item.percentile_15:
                differences.append("P15")
            if mid != item.midpoint:
                differences.append("punto medio")
            if p85 != item.percentile_85:
                differences.append("P85")
            if differences:
                issues.append(f"{definition.label}: diferencias en {', '.join(differences)}")
            rows.append(
                SourcePercentileAuditRow(
                    code=definition.code,
                    selected_value=expected,
                    rated_value=item.value,
                    observed_peers=peers,
                    rated_peers=item.peer_count,
                    observed_p15=p15,
                    rated_p15=item.percentile_15,
                    observed_midpoint=mid,
                    rated_midpoint=item.midpoint,
                    observed_p85=p85,
                    rated_p85=item.percentile_85,
                    status="REVISAR" if differences else "CUADRA",
                )
            )
        return SourcePercentileAuditResult(
            status="REVISAR" if issues else "CUADRA",
            rows=tuple(rows),
            discrepancies=tuple(issues),
        )
