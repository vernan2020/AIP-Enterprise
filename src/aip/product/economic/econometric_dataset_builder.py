from __future__ import annotations

from calendar import monthrange
from datetime import date

from aip.product.configured.repositories.economic_historical_repository import (
    EconomicHistoricalRepository,
)

from aip.product.economic.econometric_dataset import (
    EconometricDataPoint,
    EconometricMonthlyDataset,
    EconometricMonthlyRow,
)
from aip.product.economic.economic_history import (
    EconomicHistoricalObservation,
)


class EconometricDatasetBuilder:
    """
    Construye datasets econométricos reproducibles a partir
    del histórico persistido.

    Política mensual inicial:

    DAILY:
        se utiliza la última observación disponible dentro
        de cada mes.

    MONTHLY:
        se utiliza la observación oficial del período.

    Missing values:
        se conservan como None.

    Prohibido en esta capa:
        - interpolación;
        - forward-fill;
        - back-fill;
        - forecasting;
        - uso de observaciones futuras para completar
          períodos anteriores.
    """

    MONTHLY_INDICATORS = (
        "FX_SELL",
        "TPM",
        "TBP",
        "TRI_CRC_12M",
        "TRI_USD_12M",
        "INFLATION",
        "IMAE",
    )

    DAILY_TO_MONTH_END = frozenset(
        {
            "FX_SELL",
            "TPM",
            "TBP",
            "TRI_CRC_12M",
            "TRI_USD_12M",
        }
    )

    NATURAL_MONTHLY = frozenset(
        {
            "INFLATION",
            "IMAE",
        }
    )

    def __init__(
        self,
        repository: EconomicHistoricalRepository,
    ) -> None:
        self._repository = repository

    @property
    def repository(
        self,
    ) -> EconomicHistoricalRepository:
        return self._repository

    def build_monthly(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        include_incomplete: bool = True,
    ) -> EconometricMonthlyDataset:
        """
        Construye el panel mensual multivariado.

        Cuando include_incomplete=False solamente se incluyen
        períodos con información para las siete variables.
        """

        series_points: dict[
            str,
            dict[
                date,
                EconometricDataPoint,
            ],
        ] = {}

        for code in self.MONTHLY_INDICATORS:
            historical = self._repository.get_series(
                code,
                from_date=from_date,
                to_date=to_date,
            )

            series_points[code] = self._monthly_points(
                code,
                historical.observations,
            )

        periods = sorted({period for points in series_points.values() for period in points})

        rows = tuple(
            self._build_monthly_row(
                period,
                series_points,
            )
            for period in periods
        )

        if not include_incomplete:
            rows = tuple(row for row in rows if row.complete)

        data_points = tuple(
            sorted(
                (point for points in series_points.values() for point in points.values()),
                key=lambda point: (
                    point.period,
                    point.indicator_code,
                    point.observation_date,
                ),
            )
        )

        return EconometricMonthlyDataset(
            rows=rows,
            indicator_codes=(self.MONTHLY_INDICATORS),
            first_period=(rows[0].period if rows else None),
            last_period=(rows[-1].period if rows else None),
            data_points=(data_points),
        )

    def _monthly_points(
        self,
        indicator_code: str,
        observations: tuple[
            EconomicHistoricalObservation,
            ...,
        ],
    ) -> dict[
        date,
        EconometricDataPoint,
    ]:
        code = indicator_code.strip().upper()

        if code in self.DAILY_TO_MONTH_END:
            return self._aggregate_last_observation_by_month(
                code,
                observations,
            )

        if code in self.NATURAL_MONTHLY:
            return self._aggregate_monthly_observations(
                code,
                observations,
            )

        raise ValueError("Unsupported monthly econometric indicator: " f"{indicator_code}")

    @staticmethod
    def _aggregate_last_observation_by_month(
        indicator_code: str,
        observations: tuple[
            EconomicHistoricalObservation,
            ...,
        ],
    ) -> dict[
        date,
        EconometricDataPoint,
    ]:
        """
        Selecciona la última observación cronológicamente
        disponible dentro de cada mes.

        No utiliza datos de meses posteriores.
        """

        selected: dict[
            tuple[
                int,
                int,
            ],
            EconomicHistoricalObservation,
        ] = {}

        for observation in observations:
            key = (
                observation.observation_date.year,
                observation.observation_date.month,
            )

            current = selected.get(key)

            if current is None or observation.observation_date > current.observation_date:
                selected[key] = observation

        result: dict[
            date,
            EconometricDataPoint,
        ] = {}

        for (
            year,
            month,
        ), observation in selected.items():
            period = EconometricDatasetBuilder._month_end(
                year,
                month,
            )

            result[period] = EconometricDataPoint(
                indicator_code=(indicator_code),
                period=period,
                value=observation.value,
                observation_date=(observation.observation_date),
                source=observation.source,
                source_series_code=(observation.source_series_code),
            )

        return result

    @staticmethod
    def _aggregate_monthly_observations(
        indicator_code: str,
        observations: tuple[
            EconomicHistoricalObservation,
            ...,
        ],
    ) -> dict[
        date,
        EconometricDataPoint,
    ]:
        """
        Normaliza observaciones mensuales oficiales al cierre
        calendario del mismo período.

        Si existieran múltiples observaciones dentro del mismo
        mes, conserva la de fecha más reciente de ese mes.
        """

        selected: dict[
            tuple[
                int,
                int,
            ],
            EconomicHistoricalObservation,
        ] = {}

        for observation in observations:
            key = (
                observation.observation_date.year,
                observation.observation_date.month,
            )

            current = selected.get(key)

            if current is None or observation.observation_date > current.observation_date:
                selected[key] = observation

        result: dict[
            date,
            EconometricDataPoint,
        ] = {}

        for (
            year,
            month,
        ), observation in selected.items():
            period = EconometricDatasetBuilder._month_end(
                year,
                month,
            )

            result[period] = EconometricDataPoint(
                indicator_code=(indicator_code),
                period=period,
                value=observation.value,
                observation_date=(observation.observation_date),
                source=observation.source,
                source_series_code=(observation.source_series_code),
            )

        return result

    @staticmethod
    def _build_monthly_row(
        period: date,
        series_points: dict[
            str,
            dict[
                date,
                EconometricDataPoint,
            ],
        ],
    ) -> EconometricMonthlyRow:
        def value(
            code: str,
        ):
            point = series_points.get(
                code,
                {},
            ).get(period)

            return point.value if point is not None else None

        return EconometricMonthlyRow(
            period=period,
            fx_sell=value("FX_SELL"),
            tpm=value("TPM"),
            tbp=value("TBP"),
            tri_crc_12m=value("TRI_CRC_12M"),
            tri_usd_12m=value("TRI_USD_12M"),
            inflation=value("INFLATION"),
            imae=value("IMAE"),
        )

    @staticmethod
    def _month_end(
        year: int,
        month: int,
    ) -> date:
        last_day = monthrange(
            year,
            month,
        )[1]

        return date(
            year,
            month,
            last_day,
        )
