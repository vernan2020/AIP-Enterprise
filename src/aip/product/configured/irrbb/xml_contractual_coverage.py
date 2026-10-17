"""Read-only coverage assessment for contractual RTILB XML sources.

This assessment deliberately does not create cash flows or 19-band balances.
It reports whether required contractual fields are populated in each record.
No personal identifiers or financial amounts are returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "CREDIT": (
        "SaldoPrincipalOperacionCrediticia",
        "TipoMonedaOperacion",
        "FechaVencimiento",
        "FechaProximoPagoPrincipal",
        "FechaProximoPagoIntereses",
        "IndicadorTipoTasa",
    ),
    "CAPTACIONES": ("SaldoPrincipal", "TipoMonedaObligacion", "TipoTasa"),
    "BORROWING": (
        "SaldoPrincipal",
        "TipoMonedaObligacion",
        "FechaVencimiento",
        "FechaProximoPagoPrincipal",
        "FechaProximoPagoInteres",
        "TipoTasa",
    ),
    "BORROWING_MATURITY": ("SaldoaPagarPrincipal", "TipoRangoPasivo"),
}


@dataclass(frozen=True, slots=True)
class XMLContractualCoverage:
    key: str
    filename: str
    period: date
    entity_id: str
    record_count: int
    missing_by_field: tuple[tuple[str, int], ...]
    status: str


def inspect_xml_contractual_coverage(
    reader: XMLConfiaMonthlySourceReader, *, cutoff_date: date
) -> tuple[XMLContractualCoverage, ...]:
    """Inspect field presence only, never assert contractual-flow readiness.

    Some demand deposits have no contractual maturity. A present XML field is
    not proof that a complete future cash-flow schedule can be reconstructed.
    """
    results: list[XMLContractualCoverage] = []
    for key, fields in REQUIRED_FIELDS.items():
        source = reader.resolve_source(key=key, cutoff_date=cutoff_date)
        missing = {field: 0 for field in fields}
        rows = 0
        for record in reader.iter_records(source):
            rows += 1
            for field in fields:
                if not record.values.get(field, "").strip():
                    missing[field] += 1
        results.append(
            XMLContractualCoverage(
                key=key,
                filename=source.path.name,
                period=source.header.periodo,
                entity_id=source.header.id_entidad,
                record_count=rows,
                missing_by_field=tuple(missing.items()),
                status=(
                    "FIELDS_POPULATED" if rows and not any(missing.values()) else "FIELD_GAPS_FOUND"
                ),
            )
        )
    if len({result.entity_id for result in results}) != 1:
        raise ValueError("XML CONFIA contractual sources have inconsistent entity identifiers")
    if len({result.period for result in results}) != 1:
        raise ValueError("XML CONFIA contractual sources have inconsistent reporting periods")
    return tuple(results)
