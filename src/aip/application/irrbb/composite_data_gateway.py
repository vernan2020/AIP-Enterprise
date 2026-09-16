from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from aip.application.irrbb.contracts import (
    IRRBBCurveSourcePoint,
    IRRBBPositionSourceRecord,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
    IRRBBSourceSnapshot,
)
from aip.application.irrbb.ports import IRRBBDataGateway


@dataclass(frozen=True, slots=True)
class IRRBBDataGatewayBinding:
    """Name one normalized gateway without exposing its physical technology."""

    source_id: str
    gateway: IRRBBDataGateway

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("IRRBB composite gateway source_id is required")


class CompositeIRRBBDataGateway:
    """Merge certified canonical snapshots for one IRRBB valuation cutoff.

    This application-layer adapter knows nothing about Power BI, Excel, SQL or
    any other physical source. Every constituent gateway must already have crossed
    the canonical boundary. The compositor preserves traceability and fails closed
    when two sources claim the same position or provide conflicting curve points,
    preventing silent double counting in EVE/Delta EVE and SUGEF GAP.
    """

    def __init__(self, bindings: tuple[IRRBBDataGatewayBinding, ...]) -> None:
        if not bindings:
            raise ValueError("IRRBB composite gateway requires at least one binding")
        source_ids = tuple(binding.source_id for binding in bindings)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("IRRBB composite gateway source_id values must be unique")
        self._bindings = bindings

    def load_snapshot(self, *, cutoff_date: date) -> IRRBBSourceSnapshot:
        snapshots = tuple(
            (binding.source_id, binding.gateway.load_snapshot(cutoff_date=cutoff_date))
            for binding in self._bindings
        )
        for source_id, snapshot in snapshots:
            if snapshot.cutoff_date != cutoff_date:
                raise ValueError(
                    "IRRBB composite gateway received a different cutoff from "
                    f"{source_id}: {snapshot.cutoff_date.isoformat()}"
                )

        position_records, position_failures = self._merge_positions(snapshots)
        curve_points, curve_failures = self._merge_curve_points(snapshots)
        inherited_failures = self._merge_mapping_failures(snapshots)
        source_references = tuple(
            dict.fromkeys(
                source_reference
                for _, snapshot in snapshots
                for source_reference in snapshot.source_references
            )
        )

        return IRRBBSourceSnapshot(
            cutoff_date=cutoff_date,
            position_records=position_records,
            curve_points=curve_points,
            source_references=source_references,
            mapping_failures=(
                *inherited_failures,
                *position_failures,
                *curve_failures,
            ),
        )

    @staticmethod
    def _merge_positions(
        snapshots: tuple[tuple[str, IRRBBSourceSnapshot], ...],
    ) -> tuple[
        tuple[IRRBBPositionSourceRecord, ...],
        tuple[IRRBBSourceMappingFailure, ...],
    ]:
        by_position_id: dict[
            str,
            list[tuple[str, IRRBBPositionSourceRecord]],
        ] = defaultdict(list)
        for source_id, snapshot in snapshots:
            for record in snapshot.position_records:
                by_position_id[record.position.position_id].append((source_id, record))

        accepted: list[IRRBBPositionSourceRecord] = []
        failures: list[IRRBBSourceMappingFailure] = []
        for position_id, claims in by_position_id.items():
            if len(claims) == 1:
                accepted.append(claims[0][1])
                continue

            source_ids = ", ".join(source_id for source_id, _ in claims)
            source_references = " | ".join(
                dict.fromkeys(record.position.source_reference for _, record in claims)
            )
            failures.append(
                IRRBBSourceMappingFailure(
                    source_record_id=f"__composite__:duplicate-position:{position_id}",
                    source_reference=source_references,
                    code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                    canonical_field="position_id",
                    message=(
                        "Posición RTILB excluida por colisión entre fuentes canónicas "
                        f"({source_ids}); no se permite doble conteo."
                    ),
                )
            )
        return tuple(accepted), tuple(failures)

    @classmethod
    def _merge_curve_points(
        cls,
        snapshots: tuple[tuple[str, IRRBBSourceSnapshot], ...],
    ) -> tuple[tuple[IRRBBCurveSourcePoint, ...], tuple[IRRBBSourceMappingFailure, ...]]:
        by_key: dict[
            tuple[object, ...],
            list[tuple[str, IRRBBCurveSourcePoint]],
        ] = defaultdict(list)
        for source_id, snapshot in snapshots:
            for point in snapshot.curve_points:
                by_key[cls._curve_key(point)].append((source_id, point))

        accepted: list[IRRBBCurveSourcePoint] = []
        failures: list[IRRBBSourceMappingFailure] = []
        for key, claims in by_key.items():
            first = claims[0][1]
            if all(point == first for _, point in claims[1:]):
                accepted.append(first)
                continue
            if len(claims) == 1:
                accepted.append(first)
                continue

            source_ids = ", ".join(source_id for source_id, _ in claims)
            source_references = " | ".join(
                dict.fromkeys(point.source_reference for _, point in claims)
            )
            curve_id, as_of_date, currency, scenario, tenor = key
            failures.append(
                IRRBBSourceMappingFailure(
                    source_record_id=(
                        "__composite__:curve-conflict:"
                        f"{curve_id}:{as_of_date}:{currency}:{scenario}:{tenor}"
                    ),
                    source_reference=source_references,
                    code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                    canonical_field="curve_points",
                    message=(
                        "Punto de curva RTILB excluido por valores o trazabilidad "
                        f"conflictivos entre fuentes canónicas ({source_ids})."
                    ),
                )
            )
        return tuple(accepted), tuple(failures)

    @staticmethod
    def _merge_mapping_failures(
        snapshots: tuple[tuple[str, IRRBBSourceSnapshot], ...],
    ) -> tuple[IRRBBSourceMappingFailure, ...]:
        failures: list[IRRBBSourceMappingFailure] = []
        seen_ids: set[str] = set()
        for source_id, snapshot in snapshots:
            for failure in snapshot.mapping_failures:
                candidate = failure
                if candidate.source_record_id in seen_ids:
                    candidate = IRRBBSourceMappingFailure(
                        source_record_id=f"{source_id}:{failure.source_record_id}",
                        source_reference=failure.source_reference,
                        code=failure.code,
                        canonical_field=failure.canonical_field,
                        message=failure.message,
                    )
                if candidate.source_record_id in seen_ids:
                    raise ValueError(
                        "IRRBB composite gateway could not uniquely namespace mapping failure "
                        f"{failure.source_record_id!r} from {source_id}"
                    )
                seen_ids.add(candidate.source_record_id)
                failures.append(candidate)
        return tuple(failures)

    @staticmethod
    def _curve_key(point: IRRBBCurveSourcePoint) -> tuple[object, ...]:
        return (
            point.curve_id,
            point.as_of_date,
            point.currency.value,
            point.scenario.value,
            point.tenor_years,
        )
