from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricDataPoint:
    """
    Valor mensual normalizado utilizado por la capa econométrica.

    La fecha representa el período mensual de referencia.
    El dato conserva la fecha oficial de la observación utilizada
    para permitir auditoría y evitar look-ahead bias.
    """

    indicator_code: str
    period: date
    value: Decimal
    observation_date: date
    source: str
    source_series_code: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricMonthlyRow:
    """
    Fila mensual multivariada.

    Los valores faltantes se conservan explícitamente como None.
    No se realiza imputación silenciosa.
    """

    period: date

    fx_sell: Decimal | None
    tpm: Decimal | None
    tbp: Decimal | None
    tri_crc_12m: Decimal | None
    tri_usd_12m: Decimal | None
    inflation: Decimal | None
    imae: Decimal | None

    @property
    def complete(
        self,
    ) -> bool:
        return all(
            value is not None
            for value in (
                self.fx_sell,
                self.tpm,
                self.tbp,
                self.tri_crc_12m,
                self.tri_usd_12m,
                self.inflation,
                self.imae,
            )
        )


@dataclass(
    frozen=True,
    slots=True,
)
class EconometricMonthlyDataset:
    """
    Dataset mensual preparado para análisis econométrico.

    Este objeto todavía no contiene:
    - transformaciones estacionarias;
    - rezagos;
    - estimación de modelos;
    - forecasting.
    """

    rows: tuple[
        EconometricMonthlyRow,
        ...,
    ]

    indicator_codes: tuple[
        str,
        ...,
    ]

    first_period: date | None
    last_period: date | None

    data_points: tuple[
        EconometricDataPoint,
        ...,
    ] = ()

    @property
    def as_of_date(
        self,
    ) -> date | None:
        """
        Fecha real más reciente de observación contenida
        en el dataset.

        No debe confundirse con last_period, que representa
        el bucket econométrico mensual.
        """

        if not self.data_points:
            return None

        return max(
            point.observation_date
            for point
            in self.data_points
        )

    def latest_data_point(
        self,
        indicator_code: str,
    ) -> EconometricDataPoint | None:
        """
        Recupera el último punto realmente observado de
        un indicador, preservando observation_date y period.
        """

        code = (
            indicator_code
            .strip()
            .upper()
        )

        candidates = (
            point
            for point
            in self.data_points
            if (
                point.indicator_code
                .strip()
                .upper()
                == code
            )
        )

        return max(
            candidates,
            key=lambda point: (
                point.period,
                point.observation_date,
            ),
            default=None,
        )

    @property
    def row_count(
        self,
    ) -> int:
        return len(
            self.rows
        )

    @property
    def complete_row_count(
        self,
    ) -> int:
        return sum(
            1
            for row in self.rows
            if row.complete
        )

    @property
    def incomplete_row_count(
        self,
    ) -> int:
        return (
            self.row_count
            - self.complete_row_count
        )

    def complete_rows(
        self,
    ) -> tuple[
        EconometricMonthlyRow,
        ...,
    ]:
        return tuple(
            row
            for row in self.rows
            if row.complete
        )
