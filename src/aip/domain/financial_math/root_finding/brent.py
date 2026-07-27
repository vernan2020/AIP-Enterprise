from __future__ import annotations

from decimal import Decimal
from typing import Callable

from aip.domain.financial_math.exceptions import ConvergenceError, InvalidBracketError
from aip.domain.financial_math.root_finding.bisection import ConvergenceResult


def brent_solve(
    function: Callable[[Decimal], Decimal],
    lower: Decimal,
    upper: Decimal,
    *,
    tolerance: Decimal = Decimal("1e-10"),
    max_iterations: int = 100,
) -> ConvergenceResult:
    if lower >= upper:
        raise InvalidBracketError("Lower bound must be strictly less than upper bound")
    f_lower = function(lower)
    f_upper = function(upper)
    if f_lower == 0:
        return ConvergenceResult(root=lower, iterations=0, converged=True, residual=Decimal("0"), method="brent")
    if f_upper == 0:
        return ConvergenceResult(root=upper, iterations=0, converged=True, residual=Decimal("0"), method="brent")
    if f_lower * f_upper > 0:
        raise InvalidBracketError("Function values must have opposite signs at the bracket ends")
    a, b = lower, upper
    fa, fb = f_lower, f_upper
    c, fc = a, fa
    for iteration in range(1, max_iterations + 1):
        if abs(fa) <= tolerance:
            return ConvergenceResult(root=a, iterations=iteration, converged=True, residual=abs(fa), method="brent")
        if abs(fb) <= tolerance:
            return ConvergenceResult(root=b, iterations=iteration, converged=True, residual=abs(fb), method="brent")
        if fa * fb > 0:
            raise ConvergenceError("Brent did not converge")
        if abs(b - a) <= tolerance:
            return ConvergenceResult(root=(a + b) / Decimal("2"), iterations=iteration, converged=True, residual=abs(b - a), method="brent")
        s = b - fb * (b - a) / (fb - fa)
        if s <= a or s >= b:
            s = (a + b) / Decimal("2")
        f_s = function(s)
        if abs(f_s) <= tolerance:
            return ConvergenceResult(root=s, iterations=iteration, converged=True, residual=abs(f_s), method="brent")
        if fa * f_s <= 0:
            b, fb = s, f_s
        else:
            a, fa = s, f_s
    raise ConvergenceError("Brent did not converge")
