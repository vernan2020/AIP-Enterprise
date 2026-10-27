"""Safe read-only UI summary of native CONFÍA contractual reconciliation.

Only counts and categorical statuses enter the UI; no source IDs, balances,
paths, or assumed cashflows are accepted from the raw institutional sources.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from aip.domain.liquidity.cashflow.services.sugef210_projection import sugef210_windows


def _count(data: object, key: str) -> int:
    if not isinstance(data, dict):
        return 0
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def summarize_contractual_reconciliation(
    *, cutoff: date, evidence: dict[str, Any]
) -> tuple[tuple[str, str, str], ...]:
    """Convert native reference checks into 17-band UI rows, never payable cash."""
    if evidence.get("cutoff") != cutoff.isoformat():
        raise ValueError("Contractual reconciliation and current cutoff do not match")
    if evidence.get("status") != "MATCHED_REFERENCE_ONLY":
        return (
            (
                "Conciliación contractual",
                "NO DISPONIBLE",
                "La fuente no permite validar identidades; no hay pagos reconocidos.",
            ),
        )
    rows: list[tuple[str, str, str]] = []
    matched = _count(evidence, "unique_maturity_rows_matched")
    maturity = _count(evidence, "maturity_records")
    identity_issues = (
        matched != maturity
        or _count(evidence, "ambiguous_maturity_rows") > 0
        or _count(evidence, "unmatched_maturity_rows") > 0
        or _count(evidence, "maturity_rows_without_composite_identity") > 0
    )
    exact = _count(
        evidence.get("principal_reconciliation"), "distinct_contracts_reconciled_exactly"
    )
    negative = _count(
        evidence.get("principal_reconciliation"), "negative_contracts_matching_signed_band_total"
    )
    differences = _count(
        evidence.get("principal_reconciliation"), "distinct_contracts_with_principal_difference"
    )
    missing = evidence.get("contract_identities_without_maturity_bands_by_source")
    outstanding = sum(_count(missing, key) for key in ("CAPTACIONES", "BORROWING"))
    rows.extend(
        (
            (
                "Vinculación XML",
                "REVISAR" if identity_issues else "REFERENCIA",
                f"{matched} de {maturity} filas ligadas; sin pagos",
            ),
            (
                "Principal contractual",
                "REVISAR" if differences else "REFERENCIA",
                f"{exact} concilian; {negative} negativos firmados; {differences} difieren",
            ),
            (
                "Operaciones sin bandeo",
                "REVISAR" if outstanding else "REFERENCIA",
                (
                    f"{_count(missing, 'CAPTACIONES')} captaciones; "
                    f"{_count(missing, 'BORROWING')} obligaciones"
                ),
            ),
        )
    )
    dates = evidence.get("unbanded_date_evidence_by_sugef210_window")
    dates = dates if isinstance(dates, dict) else {}
    alert = dates.get("next_day_concentration_review")
    alert = alert if isinstance(alert, dict) else {}
    is_cluster = alert.get("status") == "REVIEW_SOURCE_DATE_SEMANTICS"
    if alert:
        rows.append(
            (
                "Fecha corte + 1 día",
                "REVISAR" if is_cluster else "REFERENCIA",
                (
                    f"{_count(alert, 'next_day_unbanded_contracts')} de "
                    f"{_count(alert, 'future_dated_unbanded_contracts')} fechas futuras. "
                    "No son pagos confirmados."
                ),
            )
        )
    by_window = dates.get("by_window")
    counts = by_window if isinstance(by_window, dict) else {}
    for window in sugef210_windows(cutoff):
        rows.append(
            (
                f"Ventana {window.key}",
                "SOLO FECHAS",
                f"{_count(counts, window.key)} fechas de origen; cero pagos autorizados",
            )
        )
    rows.append(
        (
            "Flujo integral CRC/USD",
            "SIN CERTIFICAR",
            "Faltan pagos aprobados y caja inicial conciliada",
        )
    )
    return tuple(rows)


_XML_CONTRACT_SOURCES = ("CREDIT", "CAPTACIONES", "BORROWING")


def summarize_approved_contractual_source_coverage(
    coverage: tuple[tuple[str, int, int], ...],
) -> tuple[dict[str, object], ...]:
    """Report all XML perimeters, including those without approved schedules.

    A missing approved schedule is unknown coverage, never zero outstanding
    contractual principal or proof that the source has no future payments.
    """
    by_key: dict[str, tuple[int, int]] = {}
    for source_key, selected, original in coverage:
        if (
            source_key not in _XML_CONTRACT_SOURCES
            or source_key in by_key
            or not isinstance(selected, int)
            or isinstance(selected, bool)
            or not isinstance(original, int)
            or isinstance(original, bool)
            or selected < 0
            or original < selected
        ):
            raise ValueError("Invalid original contractual XML source coverage")
        by_key[source_key] = selected, original
    output: list[dict[str, object]] = []
    for source_key in _XML_CONTRACT_SOURCES:
        counts = by_key.get(source_key)
        if counts is None:
            output.append(
                {
                    "source_key": source_key,
                    "status": "NO_APPROVED_CONTRACTUAL_SCHEDULE",
                    "approved_contracts": None,
                    "original_xml_contracts": None,
                    "unselected_source_records_not_automatically_cashflows": None,
                    "coverage_certified": False,
                }
            )
        else:
            selected, original = counts
            output.append(
                {
                    "source_key": source_key,
                    "status": (
                        "ALL_ORIGINAL_ROWS_SELECTED_NOT_FINANCIALLY_CERTIFIED"
                        if selected == original
                        else "PARTIALLY_SELECTED_NOT_FINANCIALLY_CERTIFIED"
                    ),
                    "approved_contracts": selected,
                    "original_xml_contracts": original,
                    "unselected_source_records_not_automatically_cashflows": original - selected,
                    "coverage_certified": False,
                }
            )
    return tuple(output)
