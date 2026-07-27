from __future__ import annotations

import math
from decimal import Decimal

from aip.domain.financial_math.exceptions import InvalidRateError


def nelson_siegel_zero_rate(tenor: Decimal, *, beta0: Decimal, beta1: Decimal, beta2: Decimal, tau: Decimal) -> Decimal:
    if tau <= 0:
        raise InvalidRateError("Tau must be positive")
    if tenor == 0:
        return beta0
    scaled = tenor / tau
    factor = (Decimal("1") - Decimal(str(math.exp(-float(scaled))))) / scaled
    return beta0 + beta1 * factor + beta2 * (factor - Decimal(str(math.exp(-float(scaled)))))


def nelson_siegel_curve(tenors: list[Decimal], *, beta0: Decimal, beta1: Decimal, beta2: Decimal, tau: Decimal) -> list[Decimal]:
    return [nelson_siegel_zero_rate(tenor, beta0=beta0, beta1=beta1, beta2=beta2, tau=tau) for tenor in tenors]
