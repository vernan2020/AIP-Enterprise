from __future__ import annotations

_RELATIVE_VALUE_CLASSIFICATION_LABELS = {
    "BARATO": "COMPRA",
    "CARO": "VENTA",
}


def relative_value_classification_label(value: object) -> str:
    """Map stable relative-value classifications to user-facing trading labels."""

    raw = str(value or "").strip()
    if not raw:
        return raw
    return _RELATIVE_VALUE_CLASSIFICATION_LABELS.get(raw.upper(), raw)
