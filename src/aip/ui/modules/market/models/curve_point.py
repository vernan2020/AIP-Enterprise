from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """Punto de curva compatible con la vista histórica de Mercado.

    ``curve_id`` y ``series`` permiten separar curva observada y modelos ajustados.
    ``label`` y ``value`` se conservan para compatibilidad con consumidores anteriores.
    """

    label: str = ""
    value: str = ""
    tenor: float | str = 0.0
    curve_id: str = ""
    series: str = "OBSERVED"
    yield_value: float = 0.0
