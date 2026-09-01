from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioRotationCandidate:
    """Preliminary institutional portfolio-rotation screening result.

    Represents a potential switch from a relatively expensive security
    currently held in the portfolio to a relatively cheap security
    available in the market.

    This object is intentionally a screening result, not an executable
    trading recommendation. Final recommendations require additional
    validation of duration, DV01, HQLA, MIL, concentration and policy limits.
    """

    # ---------------------------------------------------------
    # Posición origen
    # ---------------------------------------------------------

    source_series: str
    source_issuer: str
    source_currency: str
    source_curve_id: str

    source_spread_bp: float
    source_market_yield: float
    source_curve_yield: float
    source_tenor: float
    source_market_value_crc: float

    # ---------------------------------------------------------
    # Instrumento destino
    # ---------------------------------------------------------

    target_series: str
    target_issuer: str
    target_currency: str
    target_curve_id: str

    target_spread_bp: float
    target_market_yield: float
    target_curve_yield: float
    target_tenor: float
    target_market_price: float
    target_in_portfolio: bool

    # ---------------------------------------------------------
    # Comparación
    # ---------------------------------------------------------

    spread_improvement_bp: float
    yield_improvement_bp: float
    tenor_difference_years: float

    # ---------------------------------------------------------
    # Screening
    # ---------------------------------------------------------

    rotation_score: float
    screening_status: str
    signal_type: str

    requires_duration_review: bool
    requires_liquidity_review: bool
    requires_concentration_review: bool

    explanation: str
