from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

from aip.product.economic.econometric_dataset import (
    EconometricMonthlyDataset,
)
from aip.product.economic.econometric_diagnostics import (
    ADFTestResult,
    EconometricDiagnosticsResult,
    StationarityDiagnostic,
)


class EconometricDiagnosticsService:
    """
    Diagnósticos estadísticos previos a la estimación.

    Responsabilidades iniciales:
    - convertir el dataset mensual completo a matriz numérica;
    - ejecutar ADF en niveles;
    - ejecutar ADF en primera diferencia;
    - clasificar integración I(0), I(1) o indeterminada.

    No estima VAR, VECM ni genera forecasts.
    """

    _COLUMN_MAPPING = {
        "FX_SELL": "fx_sell",
        "TPM": "tpm",
        "TBP": "tbp",
        "TRI_CRC_12M": "tri_crc_12m",
        "TRI_USD_12M": "tri_usd_12m",
        "INFLATION": "inflation",
        "IMAE": "imae",
    }

    def __init__(
        self,
        *,
        significance_level: float = 0.05,
        minimum_observations: int = 24,
    ) -> None:
        if not (
            0.0
            < significance_level
            < 1.0
        ):
            raise ValueError(
                "significance_level must be between 0 and 1"
            )

        if minimum_observations < 12:
            raise ValueError(
                "minimum_observations must be at least 12"
            )

        self._significance_level = (
            significance_level
        )

        self._minimum_observations = (
            minimum_observations
        )

    def build_frame(
        self,
        dataset: EconometricMonthlyDataset,
    ) -> pd.DataFrame:
        """
        Convierte únicamente filas completas.

        No realiza imputación ni forward-fill.
        """

        records: list[
            dict[str, float]
        ] = []

        periods = []

        for row in dataset.rows:
            if not row.complete:
                continue

            periods.append(
                pd.Timestamp(
                    row.period
                )
            )

            records.append(
                {
                    "FX_SELL": float(
                        row.fx_sell
                    ),
                    "TPM": float(
                        row.tpm
                    ),
                    "TBP": float(
                        row.tbp
                    ),
                    "TRI_CRC_12M": float(
                        row.tri_crc_12m
                    ),
                    "TRI_USD_12M": float(
                        row.tri_usd_12m
                    ),
                    "INFLATION": float(
                        row.inflation
                    ),
                    "IMAE": float(
                        row.imae
                    ),
                }
            )

        frame = pd.DataFrame(
            records,
            index=pd.DatetimeIndex(
                periods,
                name="period",
            ),
        )

        return frame.sort_index()


    def build_series(
        self,
        dataset: EconometricMonthlyDataset,
        indicator_code: str,
    ) -> pd.Series:
        """
        Construye una serie mensual univariada utilizando toda la
        información disponible para el indicador solicitado.

        A diferencia de ``build_frame()``, este método NO exige que
        las demás variables macroeconómicas estén disponibles en el
        mismo período.

        Política:
        - no imputa valores;
        - no realiza forward-fill;
        - no utiliza observaciones futuras;
        - conserva períodos incompletos del panel cuando el indicador
          solicitado sí posee dato;
        - mantiene la fecha mensual normalizada del dataset.
        """

        code = (
            indicator_code
            .strip()
            .upper()
        )

        attribute_mapping = {
            "FX_SELL": "fx_sell",
            "TPM": "tpm",
            "TBP": "tbp",
            "TRI_CRC_12M": "tri_crc_12m",
            "TRI_USD_12M": "tri_usd_12m",
            "INFLATION": "inflation",
            "IMAE": "imae",
        }

        attribute_name = (
            attribute_mapping.get(
                code
            )
        )

        if attribute_name is None:
            raise ValueError(
                "Unsupported econometric indicator: "
                f"{indicator_code}"
            )

        periods: list[
            pd.Timestamp
        ] = []

        values: list[
            float
        ] = []

        for row in dataset.rows:
            value = getattr(
                row,
                attribute_name,
            )

            if value is None:
                continue

            numeric_value = float(
                value
            )

            if not np.isfinite(
                numeric_value
            ):
                continue

            periods.append(
                pd.Timestamp(
                    row.period
                )
            )

            values.append(
                numeric_value
            )

        series = pd.Series(
            values,
            index=pd.DatetimeIndex(
                periods,
                name="period",
            ),
            name=code,
            dtype=float,
        )

        return series.sort_index()

    def diagnose(
        self,
        dataset: EconometricMonthlyDataset,
    ) -> EconometricDiagnosticsResult:
        frame = self.build_frame(
            dataset
        )

        diagnostics = tuple(
            self._diagnose_series(
                code,
                frame[code],
            )
            for code in self._COLUMN_MAPPING
        )

        return EconometricDiagnosticsResult(
            observations=len(frame),
            diagnostics=diagnostics,
        )

    def _diagnose_series(
        self,
        indicator_code: str,
        series: pd.Series,
    ) -> StationarityDiagnostic:
        clean = (
            series
            .replace(
                [
                    np.inf,
                    -np.inf,
                ],
                np.nan,
            )
            .dropna()
            .astype(float)
        )

        level_result = (
            self._run_adf(
                indicator_code=indicator_code,
                transformation="LEVEL",
                series=clean,
            )
        )

        difference_result = (
            self._run_adf(
                indicator_code=indicator_code,
                transformation="FIRST_DIFFERENCE",
                series=clean.diff().dropna(),
            )
        )

        if level_result.stationary:
            integration_order = "I(0)"

        elif difference_result.stationary:
            integration_order = "I(1)"

        else:
            integration_order = (
                "UNDETERMINED"
            )

        return StationarityDiagnostic(
            indicator_code=indicator_code,
            level_test=level_result,
            difference_test=difference_result,
            integration_order=integration_order,
        )

    def _run_adf(
        self,
        *,
        indicator_code: str,
        transformation: str,
        series: pd.Series,
    ) -> ADFTestResult:
        observations = len(
            series
        )

        if (
            observations
            < self._minimum_observations
        ):
            return ADFTestResult(
                indicator_code=indicator_code,
                transformation=transformation,
                statistic=None,
                p_value=None,
                observations=observations,
                lags_used=None,
                critical_value_1pct=None,
                critical_value_5pct=None,
                critical_value_10pct=None,
                stationary=False,
                diagnostic=(
                    "Insufficient observations"
                ),
            )

        if series.nunique() <= 1:
            return ADFTestResult(
                indicator_code=indicator_code,
                transformation=transformation,
                statistic=None,
                p_value=None,
                observations=observations,
                lags_used=None,
                critical_value_1pct=None,
                critical_value_5pct=None,
                critical_value_10pct=None,
                stationary=False,
                diagnostic=(
                    "Constant series"
                ),
            )

        try:
            result = adfuller(
                series.to_numpy(
                    dtype=float
                ),
                regression="c",
                autolag="AIC",
                result_object=False,
            )

        except (
            ValueError,
            np.linalg.LinAlgError,
        ) as exc:
            return ADFTestResult(
                indicator_code=indicator_code,
                transformation=transformation,
                statistic=None,
                p_value=None,
                observations=observations,
                lags_used=None,
                critical_value_1pct=None,
                critical_value_5pct=None,
                critical_value_10pct=None,
                stationary=False,
                diagnostic=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        statistic = float(
            result[0]
        )

        p_value = float(
            result[1]
        )

        lags_used = int(
            result[2]
        )

        critical_values = (
            result[4]
        )

        return ADFTestResult(
            indicator_code=indicator_code,
            transformation=transformation,
            statistic=statistic,
            p_value=p_value,
            observations=observations,
            lags_used=lags_used,
            critical_value_1pct=float(
                critical_values.get(
                    "1%",
                    np.nan,
                )
            ),
            critical_value_5pct=float(
                critical_values.get(
                    "5%",
                    np.nan,
                )
            ),
            critical_value_10pct=float(
                critical_values.get(
                    "10%",
                    np.nan,
                )
            ),
            stationary=(
                p_value
                < self._significance_level
            ),
            diagnostic=None,
        )
