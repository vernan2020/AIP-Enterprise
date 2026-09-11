from __future__ import annotations

_STATUS_TRANSLATIONS = {
    "READY": "LISTO",
    "LOADED": "CARGADO",
    "LOADING": "CARGANDO",
    "AVAILABLE": "DISPONIBLE",
    "UNAVAILABLE": "NO DISPONIBLE",
    "HEALTHY": "OPERATIVO",
    "DEGRADED": "DEGRADADO",
    "WARNING": "ADVERTENCIA",
    "ERROR": "ERROR",
    "FAILED": "FALLIDO",
    "COMPLETED": "COMPLETADO",
    "CONFIGURED": "CONFIGURADO",
    "DEMO": "DEMOSTRACIÓN",
    "ACTIVE": "ACTIVO",
    "INACTIVE": "INACTIVO",
    "APPROVED": "APROBADO",
    "DRAFT": "BORRADOR",
    "PENDING": "PENDIENTE",
    "NOT_CONFIGURED": "NO CONFIGURADO",
    "NOT CONFIGURED": "NO CONFIGURADO",
    "N/A": "N/D",
}


def translate_status(value: object) -> str:
    """Translate a technical status for presentation without mutating domain values."""

    raw = str(value or "").strip()
    if not raw:
        return "N/D"
    token = raw.rsplit(".", 1)[-1].strip().upper()
    return _STATUS_TRANSLATIONS.get(token, raw)


def translate_boolean(value: object) -> str:
    """Return a Spanish presentation label for boolean-like values."""

    if isinstance(value, bool):
        return "Sí" if value else "No"
    token = str(value or "").strip().lower()
    if token in {"true", "1", "yes", "y", "si", "sí"}:
        return "Sí"
    if token in {"false", "0", "no", "n"}:
        return "No"
    return str(value)
