from __future__ import annotations

from datetime import date
from typing import Any

from aip.domain.financial_analysis.models import FinancialEntity
from aip.product.configured.readers.sugef_capital_adequacy_reader import (
    SUGEFCapitalAdequacyReader,
    _SheetObservation,
)


class SUGEFCapitalAdequacyMatrixReader(SUGEFCapitalAdequacyReader):
    """Extiende el lector SUGEF para el formato histórico horizontal oficial.

    La publicación de suficiencia patrimonial puede venir como una matriz donde
    la primera columna contiene la entidad y las columnas siguientes representan
    cortes trimestrales. Los encabezados de período se publican como fechas del
    primer día del mes, mientras que el corte regulatorio corresponde al cierre
    de ese mismo mes. La normalización de fechas heredada convierte ambos al
    mismo fin de mes antes de seleccionar la columna.

    La estrategia es deliberadamente conservadora: exige una única columna para
    el corte oficial seleccionado, una columna de entidad resoluble en el
    catálogo oficial y un conjunto suficiente de observaciones válidas. Si la
    estructura resulta ambigua, conserva el indicador como N/D.
    """

    @classmethod
    def _extract_observations(
        cls,
        rows: list[tuple[Any, ...]],
        *,
        source_cutoff: date,
        entity_index: dict[str, FinancialEntity],
    ) -> tuple[tuple[_SheetObservation, ...], str]:
        observations, strategy = super()._extract_observations(
            rows,
            source_cutoff=source_cutoff,
            entity_index=entity_index,
        )
        if observations:
            return observations, strategy

        horizontal = cls._horizontal_matrix_observations(
            rows,
            source_cutoff=source_cutoff,
            entity_index=entity_index,
        )
        if horizontal:
            return horizontal, "matriz histórica horizontal por corte"
        return (), strategy

    @classmethod
    def _horizontal_matrix_observations(
        cls,
        rows: list[tuple[Any, ...]],
        *,
        source_cutoff: date,
        entity_index: dict[str, FinancialEntity],
    ) -> tuple[_SheetObservation, ...]:
        if len(rows) < 2:
            return ()

        unique_entity_count = len({entity.entity_id for entity in entity_index.values()})
        minimum_matches = min(3, unique_entity_count)
        if minimum_matches == 0:
            return ()

        candidates: list[tuple[int, int, int, int, tuple[_SheetObservation, ...]]] = []

        for header_row, row in enumerate(rows[:20]):
            cutoff_columns = [
                column
                for column, value in enumerate(row)
                if cls._date_value(value) == source_cutoff
            ]
            if len(cutoff_columns) != 1:
                continue
            value_column = cutoff_columns[0]

            explicit_entity_columns = [
                column
                for column, value in enumerate(row)
                if cls._is_entity_header(cls._normalize(cls._text(value)))
            ]
            entity_columns = explicit_entity_columns or [
                column for column in range(len(row)) if column != value_column
            ]

            for entity_column in entity_columns:
                observations: list[_SheetObservation] = []
                seen_entities: set[str] = set()
                for row_index, data_row in enumerate(
                    rows[header_row + 1 :],
                    start=header_row + 1,
                ):
                    if max(entity_column, value_column) >= len(data_row):
                        continue
                    entity = cls._resolve_entity(
                        cls._text(data_row[entity_column]),
                        entity_index,
                    )
                    value = cls._decimal(data_row[value_column])
                    if (
                        entity is None
                        or entity.entity_id in seen_entities
                        or value is None
                        or not cls._plausible_ratio(value)
                    ):
                        continue
                    seen_entities.add(entity.entity_id)
                    observations.append(
                        _SheetObservation(
                            entity=entity,
                            value=value,
                            row_number=row_index + 1,
                        )
                    )

                if len(observations) < minimum_matches:
                    continue
                explicit_rank = 0 if entity_column in explicit_entity_columns else 1
                candidates.append(
                    (
                        explicit_rank,
                        -len(observations),
                        header_row,
                        entity_column,
                        tuple(observations),
                    )
                )

        if not candidates:
            return ()

        candidates.sort(key=lambda item: item[:4])
        best_rank = candidates[0][:2]
        best = [candidate for candidate in candidates if candidate[:2] == best_rank]
        if len(best) != 1:
            return ()
        return best[0][4]
