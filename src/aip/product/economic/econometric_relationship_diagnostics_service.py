from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import (
    variance_inflation_factor,
)
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.api import VAR
from statsmodels.tsa.vector_ar.vecm import (
    coint_johansen,
)

from aip.product.economic.econometric_dataset import (
    EconometricMonthlyDataset,
)
from aip.product.economic.econometric_diagnostics import (
    EconometricDiagnosticsResult,
)
from aip.product.economic.econometric_diagnostics_service import (
    EconometricDiagnosticsService,
)
from aip.product.economic.econometric_relationship_diagnostics import (
    CorrelationDiagnostic,
    EconometricRelationshipDiagnosticsResult,
    JohansenDiagnostic,
    LaggedRelationshipDiagnostic,
    LagSelectionDiagnostic,
    VIFDiagnostic,
)


class EconometricRelationshipDiagnosticsService:
    """
    Diagnóstico de relaciones multivariadas previo al modelado.

    Incluye:
    - correlaciones contemporáneas;
    - correlaciones rezagadas;
    - VIF;
    - selección parsimoniosa de rezagos VAR;
    - Johansen únicamente sobre variables I(1).

    Las correlaciones rezagadas son descriptivas y no deben
    interpretarse como causalidad.
    """

    def __init__(
        self,
        *,
        max_relationship_lag: int = 3,
        max_var_lags: int = 3,
        vif_warning_threshold: float = 5.0,
        vif_severe_threshold: float = 10.0,
    ) -> None:
        if max_relationship_lag < 1:
            raise ValueError(
                "max_relationship_lag must be >= 1"
            )

        if max_var_lags < 1:
            raise ValueError(
                "max_var_lags must be >= 1"
            )

        if vif_warning_threshold <= 0:
            raise ValueError(
                "vif_warning_threshold must be positive"
            )

        if (
            vif_severe_threshold
            <= vif_warning_threshold
        ):
            raise ValueError(
                "vif_severe_threshold must be greater "
                "than vif_warning_threshold"
            )

        self._max_relationship_lag = (
            max_relationship_lag
        )

        self._max_var_lags = (
            max_var_lags
        )

        self._vif_warning_threshold = (
            vif_warning_threshold
        )

        self._vif_severe_threshold = (
            vif_severe_threshold
        )

        self._frame_builder = (
            EconometricDiagnosticsService()
        )

    def diagnose(
        self,
        dataset: EconometricMonthlyDataset,
        stationarity: EconometricDiagnosticsResult,
    ) -> EconometricRelationshipDiagnosticsResult:
        frame = (
            self._frame_builder
            .build_frame(
                dataset
            )
        )

        stationary_frame = (
            self._build_stationary_frame(
                frame,
                stationarity,
            )
        )

        correlations = (
            self._correlations(
                frame
            )
        )

        lagged = (
            self._lagged_relationships(
                stationary_frame
            )
        )

        vif = (
            self._vif(
                stationary_frame
            )
        )

        lag_selection = (
            self._lag_selection(
                stationary_frame
            )
        )

        johansen = (
            self._johansen(
                frame,
                stationarity,
            )
        )

        return (
            EconometricRelationshipDiagnosticsResult(
                observations=len(frame),
                correlations=correlations,
                lagged_relationships=lagged,
                vif=vif,
                lag_selection=lag_selection,
                johansen=johansen,
            )
        )

    @staticmethod
    def _build_stationary_frame(
        frame: pd.DataFrame,
        stationarity: EconometricDiagnosticsResult,
    ) -> pd.DataFrame:
        """
        Construye una matriz estacionaria:

        I(0):
            permanece en nivel.

        I(1):
            primera diferencia.

        UNDETERMINED:
            se excluye.
        """

        transformed: dict[
            str,
            pd.Series,
        ] = {}

        i0 = set(
            stationarity.stationary_in_levels
        )

        i1 = set(
            stationarity.integrated_order_one
        )

        for column in frame.columns:
            if column in i0:
                transformed[
                    column
                ] = frame[
                    column
                ]

            elif column in i1:
                transformed[
                    column
                ] = (
                    frame[
                        column
                    ].diff()
                )

        if not transformed:
            return pd.DataFrame(
                index=frame.index
            )

        return (
            pd.DataFrame(
                transformed,
                index=frame.index,
            )
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

    @staticmethod
    def _correlations(
        frame: pd.DataFrame,
    ) -> tuple[
        CorrelationDiagnostic,
        ...,
    ]:
        if frame.empty:
            return ()

        matrix = frame.corr(
            method="pearson"
        )

        columns = tuple(
            matrix.columns
        )

        output: list[
            CorrelationDiagnostic
        ] = []

        for left_index, left in enumerate(
            columns
        ):
            for right in columns[
                left_index + 1:
            ]:
                value = matrix.loc[
                    left,
                    right,
                ]

                if pd.isna(
                    value
                ):
                    continue

                output.append(
                    CorrelationDiagnostic(
                        left_indicator=str(
                            left
                        ),
                        right_indicator=str(
                            right
                        ),
                        coefficient=float(
                            value
                        ),
                    )
                )

        return tuple(
            output
        )

    def _lagged_relationships(
        self,
        frame: pd.DataFrame,
    ) -> tuple[
        LaggedRelationshipDiagnostic,
        ...,
    ]:
        if frame.empty:
            return ()

        output: list[
            LaggedRelationshipDiagnostic
        ] = []

        for driver in frame.columns:
            for target in frame.columns:
                if driver == target:
                    continue

                for lag in range(
                    1,
                    self._max_relationship_lag + 1,
                ):
                    aligned = pd.concat(
                        [
                            frame[
                                driver
                            ].shift(
                                lag
                            ).rename(
                                "driver"
                            ),
                            frame[
                                target
                            ].rename(
                                "target"
                            ),
                        ],
                        axis=1,
                    ).dropna()

                    if len(
                        aligned
                    ) < 12:
                        continue

                    if (
                        aligned[
                            "driver"
                        ].nunique()
                        <= 1
                        or aligned[
                            "target"
                        ].nunique()
                        <= 1
                    ):
                        continue

                    coefficient = (
                        aligned[
                            "driver"
                        ].corr(
                            aligned[
                                "target"
                            ]
                        )
                    )

                    if pd.isna(
                        coefficient
                    ):
                        continue

                    output.append(
                        LaggedRelationshipDiagnostic(
                            driver=str(
                                driver
                            ),
                            target=str(
                                target
                            ),
                            lag=lag,
                            coefficient=float(
                                coefficient
                            ),
                            observations=len(
                                aligned
                            ),
                        )
                    )

        return tuple(
            output
        )

    def _vif(
        self,
        frame: pd.DataFrame,
    ) -> tuple[
        VIFDiagnostic,
        ...,
    ]:
        if (
            frame.empty
            or frame.shape[1] < 2
        ):
            return ()

        standardized = (
            frame
            - frame.mean()
        )

        standard_deviation = (
            frame.std(
                ddof=0
            )
        )

        usable_columns = [
            column
            for column
            in frame.columns
            if (
                standard_deviation[
                    column
                ]
                > 0
            )
        ]

        if len(
            usable_columns
        ) < 2:
            return ()

        standardized = (
            standardized[
                usable_columns
            ]
            / standard_deviation[
                usable_columns
            ]
        )

        matrix = add_constant(
            standardized,
            has_constant="add",
        ).to_numpy(
            dtype=float
        )

        output: list[
            VIFDiagnostic
        ] = []

        for index, code in enumerate(
            usable_columns,
            start=1,
        ):
            try:
                captured_warnings: list[
                    warnings.WarningMessage
                ] = []

                with warnings.catch_warnings(
                    record=True
                ) as warning_records:
                    warnings.simplefilter(
                        "always"
                    )

                    value = float(
                        variance_inflation_factor(
                            matrix,
                            index,
                            standardize=False,
                        )
                    )

                    captured_warnings = list(
                        warning_records
                    )

                warning_diagnostic = (
                    " | ".join(
                        str(
                            item.message
                        )
                        for item
                        in captured_warnings
                    )
                    if captured_warnings
                    else None
                )

                if not math.isfinite(
                    value
                ):
                    status = "SEVERE"

                elif (
                    value
                    >= self._vif_severe_threshold
                ):
                    status = "SEVERE"

                elif (
                    value
                    >= self._vif_warning_threshold
                ):
                    status = "WARNING"

                else:
                    status = "OK"

                # Una advertencia de condicionamiento numérico
                # nunca debe degradarse silenciosamente a OK.
                if (
                    captured_warnings
                    and status == "OK"
                ):
                    status = "WARNING"

                output.append(
                    VIFDiagnostic(
                        indicator_code=str(
                            code
                        ),
                        vif=value,
                        status=status,
                        diagnostic=(
                            warning_diagnostic
                        ),
                    )
                )

            except (
                ValueError,
                np.linalg.LinAlgError,
                FloatingPointError,
            ) as exc:
                output.append(
                    VIFDiagnostic(
                        indicator_code=str(
                            code
                        ),
                        vif=None,
                        status="UNAVAILABLE",
                        diagnostic=(
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

        return tuple(
            output
        )

    def _lag_selection(
        self,
        frame: pd.DataFrame,
    ) -> LagSelectionDiagnostic:
        observations = len(
            frame
        )

        variables = int(
            frame.shape[1]
        )

        if (
            observations < 20
            or variables < 2
        ):
            return LagSelectionDiagnostic(
                observations=observations,
                variables=variables,
                maxlags_evaluated=0,
                aic=None,
                bic=None,
                hqic=None,
                fpe=None,
                diagnostic=(
                    "Insufficient data for VAR lag selection"
                ),
            )

        # Restricción de parsimonia.
        #
        # Evita pedir más rezagos de los que la muestra puede
        # razonablemente soportar.
        sample_limit = max(
            1,
            (
                observations
                - 2
            )
            // (
                variables
                + 1
            ),
        )

        maxlags = min(
            self._max_var_lags,
            sample_limit,
        )

        try:
            selection = (
                VAR(
                    frame.to_numpy(
                        dtype=float,
                    )
                )
                .select_order(
                    maxlags=maxlags
                )
            )

            selected = (
                selection.selected_orders
            )

            return LagSelectionDiagnostic(
                observations=observations,
                variables=variables,
                maxlags_evaluated=maxlags,
                aic=self._as_optional_int(
                    selected.get(
                        "aic"
                    )
                ),
                bic=self._as_optional_int(
                    selected.get(
                        "bic"
                    )
                ),
                hqic=self._as_optional_int(
                    selected.get(
                        "hqic"
                    )
                ),
                fpe=self._as_optional_int(
                    selected.get(
                        "fpe"
                    )
                ),
                diagnostic=None,
            )

        except (
            ValueError,
            np.linalg.LinAlgError,
        ) as exc:
            return LagSelectionDiagnostic(
                observations=observations,
                variables=variables,
                maxlags_evaluated=maxlags,
                aic=None,
                bic=None,
                hqic=None,
                fpe=None,
                diagnostic=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    @staticmethod
    def _johansen(
        frame: pd.DataFrame,
        stationarity: EconometricDiagnosticsResult,
    ) -> JohansenDiagnostic:
        i1_variables = tuple(
            code
            for code
            in stationarity.integrated_order_one
            if code in frame.columns
        )

        if len(
            i1_variables
        ) < 2:
            return JohansenDiagnostic(
                variables=i1_variables,
                observations=0,
                deterministic_order=0,
                lag_differences=1,
                rank_5pct=None,
                trace_statistics=(),
                critical_values_5pct=(),
                diagnostic=(
                    "At least two I(1) variables are required"
                ),
            )

        johansen_frame = (
            frame[
                list(
                    i1_variables
                )
            ]
            .dropna()
            .astype(float)
        )

        observations = len(
            johansen_frame
        )

        if observations < 24:
            return JohansenDiagnostic(
                variables=i1_variables,
                observations=observations,
                deterministic_order=0,
                lag_differences=1,
                rank_5pct=None,
                trace_statistics=(),
                critical_values_5pct=(),
                diagnostic=(
                    "Insufficient observations for Johansen"
                ),
            )

        deterministic_order = 0
        lag_differences = 1

        try:
            result = coint_johansen(
                johansen_frame.to_numpy(
                    dtype=float
                ),
                det_order=(
                    deterministic_order
                ),
                k_ar_diff=(
                    lag_differences
                ),
            )

        except (
            ValueError,
            np.linalg.LinAlgError,
        ) as exc:
            return JohansenDiagnostic(
                variables=i1_variables,
                observations=observations,
                deterministic_order=(
                    deterministic_order
                ),
                lag_differences=(
                    lag_differences
                ),
                rank_5pct=None,
                trace_statistics=(),
                critical_values_5pct=(),
                diagnostic=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        trace_statistics = tuple(
            float(
                value
            )
            for value in result.lr1
        )

        critical_values = tuple(
            float(
                row[1]
            )
            for row in result.cvt
        )

        rank = 0

        for statistic, critical in zip(
            trace_statistics,
            critical_values,
            strict=True,
        ):
            if statistic > critical:
                rank += 1
            else:
                break

        return JohansenDiagnostic(
            variables=i1_variables,
            observations=observations,
            deterministic_order=(
                deterministic_order
            ),
            lag_differences=(
                lag_differences
            ),
            rank_5pct=rank,
            trace_statistics=(
                trace_statistics
            ),
            critical_values_5pct=(
                critical_values
            ),
            diagnostic=None,
        )

    @staticmethod
    def _as_optional_int(
        value,
    ) -> int | None:
        if value is None:
            return None

        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None
