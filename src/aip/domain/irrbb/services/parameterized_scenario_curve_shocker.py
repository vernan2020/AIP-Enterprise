from __future__ import annotations

from decimal import Decimal

from aip.domain.irrbb.models import IRRBBScenario, ScenarioShockCalibration
from aip.domain.irrbb.ports import ScenarioTenorShockProvider

_BASIS_POINTS_PER_UNIT = Decimal("10000")


class ParameterizedScenarioCurveShocker:
    """Apply an externally supplied signed tenor shock to a base zero/reference rate.

    The service contains no steepener/flattener formula. A methodology-specific
    ``ScenarioTenorShockProvider`` supplies the signed basis-point shock for each
    tenor. This keeps prospective SUGEF, Basel-aligned and internal scenarios
    versionable without changing the calculation service.
    """

    def __init__(self, shock_provider: ScenarioTenorShockProvider) -> None:
        self._shock_provider = shock_provider

    def shocked_rate(
        self,
        *,
        base_rate: Decimal,
        tenor_years: Decimal,
        scenario: IRRBBScenario,
        calibration: ScenarioShockCalibration,
    ) -> Decimal:
        if tenor_years < 0:
            raise ValueError("tenor_years cannot be negative")
        if scenario is IRRBBScenario.BASE:
            return base_rate

        shock_bp = self._shock_provider.shock_basis_points(
            currency=calibration.currency,
            scenario=scenario,
            tenor_years=tenor_years,
            calibration=calibration,
        )
        return base_rate + (shock_bp / _BASIS_POINTS_PER_UNIT)


class ParallelOnlyScenarioTenorShockProvider:
    """Use only the parallel shock magnitude explicitly available in calibration.

    Non-parallel scenarios deliberately fail until an approved tenor transformation
    is supplied. This is safer than inventing a short/long interpolation merely from
    headline calibration magnitudes.
    """

    def shock_basis_points(
        self,
        *,
        currency: object,
        scenario: IRRBBScenario,
        tenor_years: Decimal,
        calibration: ScenarioShockCalibration,
    ) -> Decimal:
        del currency, tenor_years
        if scenario is IRRBBScenario.PARALLEL_UP:
            return calibration.parallel_bp
        if scenario is IRRBBScenario.PARALLEL_DOWN:
            return -calibration.parallel_bp
        raise ValueError(
            f"scenario {scenario.value} requires an approved non-parallel tenor-shock methodology"
        )
