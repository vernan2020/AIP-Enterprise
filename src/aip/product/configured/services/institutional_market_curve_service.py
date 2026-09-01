from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True, slots=True)
class CurveFitMetrics:
    """Goodness-of-fit metrics for an institutional curve calibration."""

    rmse: Decimal
    mae: Decimal
    r_squared: Decimal


@dataclass(frozen=True, slots=True)
class NelsonSiegelCalibration:
    """Calibrated Nelson-Siegel parameters and diagnostics."""

    beta0: Decimal
    beta1: Decimal
    beta2: Decimal
    tau: Decimal
    metrics: CurveFitMetrics


@dataclass(frozen=True, slots=True)
class PolynomialDegree2Curve:
    """Second-degree polynomial coefficients."""

    a: Decimal
    b: Decimal
    c: Decimal


@dataclass(frozen=True, slots=True)
class PolynomialDegree2Calibration:
    """Second-degree polynomial calibration and diagnostics."""

    curve: PolynomialDegree2Curve
    metrics: CurveFitMetrics


@dataclass(frozen=True, slots=True)
class InstitutionalMarketCurveResult:
    """Calibrated institutional market curve built from PiPCA observations."""

    curve_id: str
    observations: tuple[tuple[Decimal, Decimal], ...]
    observation_count: int
    min_tenor: Decimal
    max_tenor: Decimal
    nelson_siegel: NelsonSiegelCalibration
    polynomial_degree2: PolynomialDegree2Calibration


class InstitutionalMarketCurveService:
    """Build Coopealianza institutional curves from the PiPCA market universe.

    The service intentionally operates on observed PiPCA yield/maturity pairs
    only.  It never fabricates a curve when the source universe does not have
    enough independent tenor observations to support calibration.

    Nelson-Siegel is calibrated by profiling a deterministic grid of positive
    tau values.  Conditional on each tau, beta0/beta1/beta2 are obtained by
    ordinary least squares.  The tau producing the lowest in-sample RMSE is
    retained.  A quadratic OLS fit is calculated in parallel as a diagnostic
    benchmark; the configured provider exposes Nelson-Siegel as the official
    model.
    """

    MIN_OBSERVATIONS = 4
    _EPSILON = 1.0e-12

    _CURVE_RULES: tuple[tuple[str, str, str], ...] = (
        ("GOBIERNO_CRC", "G", "tp"),
        ("GOBIERNO_USD", "G", "tp$"),
        ("BCCR_CRC", "BCCR", "bem"),
    )

    _TAU_GRID: tuple[float, ...] = (
        0.25,
        0.50,
        0.75,
        1.00,
        1.50,
        2.00,
        3.00,
        4.00,
        5.00,
        7.00,
        10.00,
        15.00,
        20.00,
        30.00,
    )

    def build_curves(
        self,
        vector_records: list[dict[str, Any]],
        cutoff_date: date,
    ) -> tuple[InstitutionalMarketCurveResult, ...]:
        """Calibrate every supported curve for the supplied valuation date."""
        if not isinstance(cutoff_date, date):
            raise TypeError("cutoff_date must be datetime.date")

        results: list[InstitutionalMarketCurveResult] = []

        for curve_id, issuer_code, mnemonic_code in self._CURVE_RULES:
            observations = self._collect_observations(
                vector_records=vector_records,
                cutoff_date=cutoff_date,
                issuer_code=issuer_code,
                mnemonic_code=mnemonic_code,
            )

            if len(observations) < self.MIN_OBSERVATIONS:
                continue

            if len({tenor for tenor, _ in observations}) < 3:
                continue

            nelson_siegel = self._fit_nelson_siegel(observations)
            polynomial = self._fit_polynomial_degree2(observations)

            if nelson_siegel is None or polynomial is None:
                continue

            tenors = tuple(tenor for tenor, _ in observations)
            results.append(
                InstitutionalMarketCurveResult(
                    curve_id=curve_id,
                    observations=observations,
                    observation_count=len(observations),
                    min_tenor=min(tenors),
                    max_tenor=max(tenors),
                    nelson_siegel=nelson_siegel,
                    polynomial_degree2=polynomial,
                )
            )

        return tuple(results)

    @classmethod
    def _collect_observations(
        cls,
        *,
        vector_records: list[dict[str, Any]],
        cutoff_date: date,
        issuer_code: str,
        mnemonic_code: str,
    ) -> tuple[tuple[Decimal, Decimal], ...]:
        observations: list[tuple[Decimal, Decimal]] = []
        seen: set[tuple[str, str, str]] = set()

        for record in vector_records:
            if not isinstance(record, dict):
                continue

            issuer = str(record.get("issuer") or "").strip().upper()
            mnemonic = str(
                record.get("instrument_type_or_mnemonic") or ""
            ).strip().lower()

            if issuer != issuer_code or mnemonic != mnemonic_code:
                continue

            maturity = record.get("maturity_date_if_present")
            if isinstance(maturity, datetime):
                maturity = maturity.date()
            if not isinstance(maturity, date) or maturity <= cutoff_date:
                continue

            market_yield = cls._decimal(record.get("market_yield"))
            if market_yield is None or market_yield <= 0:
                continue

            tenor = Decimal(str((maturity - cutoff_date).days / 365.25))
            if tenor <= 0:
                continue

            series = str(record.get("series_or_security_code") or "").strip().upper()
            isin = str(record.get("isin_if_present") or "").strip().upper()
            identity = (
                series or isin or maturity.isoformat(),
                maturity.isoformat(),
                str(market_yield),
            )
            if identity in seen:
                continue
            seen.add(identity)
            observations.append((tenor, market_yield))

        observations.sort(key=lambda item: (item[0], item[1]))
        return tuple(observations)

    @classmethod
    def _fit_nelson_siegel(
        cls,
        observations: tuple[tuple[Decimal, Decimal], ...],
    ) -> NelsonSiegelCalibration | None:
        x = [float(tenor) for tenor, _ in observations]
        y = [float(rate) for _, rate in observations]

        best: tuple[float, tuple[float, float, float], CurveFitMetrics] | None = None

        for tau in cls._TAU_GRID:
            design: list[tuple[float, float, float]] = []
            for tenor in x:
                scaled = tenor / tau
                if abs(scaled) <= cls._EPSILON:
                    level = 1.0
                    curvature = 0.0
                else:
                    decay = math.exp(-scaled)
                    level = (1.0 - decay) / scaled
                    curvature = level - decay
                design.append((1.0, level, curvature))

            coefficients = cls._least_squares_3(design, y)
            if coefficients is None:
                continue

            predicted = [
                row[0] * coefficients[0]
                + row[1] * coefficients[1]
                + row[2] * coefficients[2]
                for row in design
            ]
            metrics = cls._metrics(y, predicted)
            rmse = float(metrics.rmse)

            if best is None or rmse < best[0] - cls._EPSILON:
                best = (rmse, coefficients, metrics)

        if best is None:
            return None

        _, coefficients, metrics = best
        # Re-identify the selected tau deterministically from the fit RMSE.
        selected_tau: float | None = None
        selected_rmse = float(metrics.rmse)
        for tau in cls._TAU_GRID:
            design = []
            for tenor in x:
                scaled = tenor / tau
                decay = math.exp(-scaled)
                level = (1.0 - decay) / scaled
                design.append((1.0, level, level - decay))
            candidate = cls._least_squares_3(design, y)
            if candidate is None:
                continue
            predicted = [
                row[0] * candidate[0]
                + row[1] * candidate[1]
                + row[2] * candidate[2]
                for row in design
            ]
            if abs(float(cls._metrics(y, predicted).rmse) - selected_rmse) <= cls._EPSILON:
                selected_tau = tau
                coefficients = candidate
                break

        if selected_tau is None:
            return None

        return NelsonSiegelCalibration(
            beta0=cls._to_decimal(coefficients[0]),
            beta1=cls._to_decimal(coefficients[1]),
            beta2=cls._to_decimal(coefficients[2]),
            tau=cls._to_decimal(selected_tau),
            metrics=metrics,
        )

    @classmethod
    def _fit_polynomial_degree2(
        cls,
        observations: tuple[tuple[Decimal, Decimal], ...],
    ) -> PolynomialDegree2Calibration | None:
        x = [float(tenor) for tenor, _ in observations]
        y = [float(rate) for _, rate in observations]
        design = [(1.0, tenor, tenor * tenor) for tenor in x]
        coefficients = cls._least_squares_3(design, y)
        if coefficients is None:
            return None

        predicted = [
            row[0] * coefficients[0]
            + row[1] * coefficients[1]
            + row[2] * coefficients[2]
            for row in design
        ]

        return PolynomialDegree2Calibration(
            curve=PolynomialDegree2Curve(
                a=cls._to_decimal(coefficients[0]),
                b=cls._to_decimal(coefficients[1]),
                c=cls._to_decimal(coefficients[2]),
            ),
            metrics=cls._metrics(y, predicted),
        )

    @classmethod
    def _least_squares_3(
        cls,
        design: list[tuple[float, float, float]],
        targets: list[float],
    ) -> tuple[float, float, float] | None:
        if len(design) != len(targets) or len(design) < 3:
            return None

        matrix = [[0.0] * 3 for _ in range(3)]
        rhs = [0.0, 0.0, 0.0]

        for row, target in zip(design, targets, strict=True):
            if not all(math.isfinite(value) for value in (*row, target)):
                return None
            for i in range(3):
                rhs[i] += row[i] * target
                for j in range(3):
                    matrix[i][j] += row[i] * row[j]

        augmented = [matrix[i][:] + [rhs[i]] for i in range(3)]

        for pivot_index in range(3):
            pivot_row = max(
                range(pivot_index, 3),
                key=lambda row_index: abs(augmented[row_index][pivot_index]),
            )
            if abs(augmented[pivot_row][pivot_index]) <= cls._EPSILON:
                return None
            if pivot_row != pivot_index:
                augmented[pivot_index], augmented[pivot_row] = (
                    augmented[pivot_row],
                    augmented[pivot_index],
                )

            pivot = augmented[pivot_index][pivot_index]
            for column in range(pivot_index, 4):
                augmented[pivot_index][column] /= pivot

            for row_index in range(3):
                if row_index == pivot_index:
                    continue
                factor = augmented[row_index][pivot_index]
                for column in range(pivot_index, 4):
                    augmented[row_index][column] -= factor * augmented[pivot_index][column]

        solution = tuple(augmented[index][3] for index in range(3))
        if not all(math.isfinite(value) for value in solution):
            return None
        return solution

    @classmethod
    def _metrics(
        cls,
        actual: list[float],
        predicted: list[float],
    ) -> CurveFitMetrics:
        residuals = [a - p for a, p in zip(actual, predicted, strict=True)]
        count = len(residuals)
        mse = sum(value * value for value in residuals) / count
        rmse = math.sqrt(max(mse, 0.0))
        mae = sum(abs(value) for value in residuals) / count

        mean = sum(actual) / count
        total_sum_squares = sum((value - mean) ** 2 for value in actual)
        residual_sum_squares = sum(value * value for value in residuals)
        if total_sum_squares <= cls._EPSILON:
            r_squared = 1.0 if residual_sum_squares <= cls._EPSILON else 0.0
        else:
            r_squared = 1.0 - residual_sum_squares / total_sum_squares

        return CurveFitMetrics(
            rmse=cls._to_decimal(rmse),
            mae=cls._to_decimal(mae),
            r_squared=cls._to_decimal(r_squared),
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            result = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            return None
        if not result.is_finite():
            return None
        return result

    @staticmethod
    def _to_decimal(value: float) -> Decimal:
        return Decimal(str(value))
