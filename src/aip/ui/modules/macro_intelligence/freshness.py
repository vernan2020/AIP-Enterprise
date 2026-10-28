"""Presentation-only warning for lagging official economic observations."""

from __future__ import annotations

from datetime import date

from aip.product.economic.economic_viewmodel import EconomicSnapshot


def economic_source_freshness_notice(snapshot: EconomicSnapshot, *, as_of: date) -> str:
    """Different release frequencies require different freshness windows.

    No observed value or source timestamp is changed by this check.
    """
    sensitive_windows = {"FX_SELL": 7, "TPM": 10, "TBP": 10}
    outdated: list[str] = []
    for card in snapshot.market_snapshot:
        threshold = sensitive_windows.get(card.code)
        if threshold is None:
            continue
        if card.observation_date is None:
            outdated.append(f"{card.code}: sin fecha")
        elif (as_of - card.observation_date).days > threshold:
            outdated.append(f"{card.code}: {card.observation_date:%d/%m/%Y}")
    historical = "HISTÓRICO LOCAL" in snapshot.source.upper()
    upstream_failed = any("HTTP 500" in item for item in snapshot.diagnostics)
    if not outdated and not historical:
        return ""
    if upstream_failed:
        reason = "El servicio oficial BCCR respondió HTTP 500; se presenta histórico institucional."
    elif historical:
        reason = "Sin actualización BCCR en línea; se presenta histórico institucional."
    else:
        reason = "Algunos indicadores BCCR requieren revisión de vigencia."
    detail = "; ".join(outdated) if outdated else "Sin confirmación de conexión en línea"
    advice = (
        "Servicio BCCR temporalmente no disponible; reintentar actualización."
        if upstream_failed
        else "Revisar token en la sesión CONFIGURED y conexión BCCR."
    )
    return f"AVISO DE VIGENCIA — {reason} Últimas observaciones: {detail}. {advice}"
