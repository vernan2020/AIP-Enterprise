from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from aip.infrastructure.configuration.models import (
    DatabaseSettings,
)
from aip.infrastructure.database.manager import (
    DatabaseManager,
)
from aip.product.economic.economic_history import (
    EconomicHistoricalObservation,
)


class EconomicHistoricalStore:
    """
    Store persistente de series macroeconómicas.

    Responsabilidades:
    - persistir observaciones económicas normalizadas;
    - evitar duplicados por indicador y fecha;
    - permitir consultas por rango temporal;
    - exponer estadísticas físicas del histórico.

    No contiene:
    - forecasting;
    - interpolación;
    - resampling;
    - correlaciones;
    - escenarios;
    - reglas econométricas.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        database_settings: DatabaseSettings | None = None,
    ) -> None:
        if project_root is None:
            project_root = Path(__file__).resolve().parents[5]

        self._project_root = project_root

        self._database = DatabaseManager(
            database_settings or DatabaseSettings(),
            project_root,
        )

        self._initialized = False

    @property
    def database_path(
        self,
    ) -> Path:
        return self._database.path

    def initialize(
        self,
    ) -> None:
        if self._initialized:
            return

        self._database.initialize()
        self._create_schema()
        self._initialized = True

    def close(
        self,
    ) -> None:
        if not self._initialized:
            return

        self._database.close()
        self._initialized = False

    def __enter__(
        self,
    ) -> "EconomicHistoricalStore":
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

    def _create_schema(
        self,
    ) -> None:
        connection = self._database.connection

        connection.execute("""
            CREATE TABLE IF NOT EXISTS
            economic_history_observations (
                indicator_code VARCHAR NOT NULL,
                observation_date DATE NOT NULL,
                value VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                source_series_code VARCHAR,
                unit VARCHAR NOT NULL,
                frequency VARCHAR NOT NULL,
                updated_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (
                    indicator_code,
                    observation_date
                )
            )
            """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_economic_history_code_date
            ON economic_history_observations (
                indicator_code,
                observation_date
            )
            """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_economic_history_date
            ON economic_history_observations (
                observation_date
            )
            """)

    def upsert_observations(
        self,
        observations: Iterable[EconomicHistoricalObservation],
    ) -> int:
        """
        Inserta o actualiza observaciones.

        Retorna el número de observaciones recibidas
        y procesadas por el store.
        """

        self.initialize()

        materialized = tuple(observations)

        if not materialized:
            return 0

        payload = [
            (
                item.indicator_code,
                item.observation_date,
                str(item.value),
                item.source,
                item.source_series_code,
                item.unit,
                item.frequency,
            )
            for item in materialized
        ]

        connection = self._database.connection

        try:
            connection.execute("BEGIN TRANSACTION")

            connection.executemany(
                """
                INSERT INTO
                economic_history_observations (
                    indicator_code,
                    observation_date,
                    value,
                    source,
                    source_series_code,
                    unit,
                    frequency,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, now()
                )

                ON CONFLICT (
                    indicator_code,
                    observation_date
                )

                DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    source_series_code =
                        excluded.source_series_code,
                    unit = excluded.unit,
                    frequency =
                        excluded.frequency,
                    updated_at = now()
                """,
                payload,
            )

            connection.execute("COMMIT")

        except Exception:
            connection.execute("ROLLBACK")
            raise

        return len(materialized)

    def observations_for_series(
        self,
        *,
        indicator_code: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[
        EconomicHistoricalObservation,
        ...,
    ]:
        self.initialize()

        normalized_code = indicator_code.strip().upper()

        if not normalized_code:
            return ()

        clauses = ["indicator_code = ?"]

        parameters: list[object] = [normalized_code]

        if from_date is not None:
            clauses.append("observation_date >= ?")
            parameters.append(from_date)

        if to_date is not None:
            clauses.append("observation_date <= ?")
            parameters.append(to_date)

        where_clause = " AND ".join(clauses)

        rows = self._database.connection.execute(
            f"""
                SELECT
                    indicator_code,
                    observation_date,
                    value,
                    source,
                    source_series_code,
                    unit,
                    frequency

                FROM
                    economic_history_observations

                WHERE
                    {where_clause}

                ORDER BY
                    observation_date
                """,
            parameters,
        ).fetchall()

        return tuple(
            EconomicHistoricalObservation(
                indicator_code=str(row[0]),
                observation_date=row[1],
                value=Decimal(str(row[2])),
                source=str(row[3]),
                source_series_code=(None if row[4] is None else str(row[4])),
                unit=str(row[5]),
                frequency=str(row[6]),
            )
            for row in rows
        )

    def latest_observation(
        self,
        *,
        indicator_code: str,
    ) -> EconomicHistoricalObservation | None:
        observations = self.observations_for_series(indicator_code=(indicator_code))

        if not observations:
            return None

        return observations[-1]

    def available_dates(
        self,
        *,
        indicator_code: str,
    ) -> tuple[
        date,
        ...,
    ]:
        self.initialize()

        normalized_code = indicator_code.strip().upper()

        if not normalized_code:
            return ()

        rows = self._database.connection.execute(
            """
                SELECT
                    observation_date

                FROM
                    economic_history_observations

                WHERE
                    indicator_code = ?

                ORDER BY
                    observation_date
                """,
            [normalized_code],
        ).fetchall()

        return tuple(row[0] for row in rows)

    def series_codes(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        self.initialize()

        rows = self._database.connection.execute("""
                SELECT DISTINCT
                    indicator_code

                FROM
                    economic_history_observations

                ORDER BY
                    indicator_code
                """).fetchall()

        return tuple(str(row[0]) for row in rows)

    def statistics(
        self,
    ) -> dict[
        str,
        int,
    ]:
        self.initialize()

        connection = self._database.connection

        observations = connection.execute("""
                SELECT COUNT(*)
                FROM economic_history_observations
                """).fetchone()[0]

        series = connection.execute("""
                SELECT COUNT(
                    DISTINCT indicator_code
                )
                FROM economic_history_observations
                """).fetchone()[0]

        dates = connection.execute("""
                SELECT COUNT(
                    DISTINCT observation_date
                )
                FROM economic_history_observations
                """).fetchone()[0]

        return {
            "observations": int(observations),
            "series": int(series),
            "dates": int(dates),
        }
