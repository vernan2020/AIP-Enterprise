from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir

from aip.product.economic.economic_viewmodel import (
    EconomicCurvePoint,
    EconomicIndicatorCard,
    EconomicSnapshot,
)
from aip.shared.serialization import JsonSerializer

logger = logging.getLogger(__name__)


class EconomicSnapshotStore:
    """
    Persistencia local del último snapshot macroeconómico válido.

    Responsabilidades:
    - almacenar el último EconomicSnapshot disponible;
    - reconstruir el snapshot preservando Decimal y date;
    - versionar el formato persistido;
    - tolerar archivos inexistentes, corruptos o incompatibles;
    - realizar escritura atómica.

    No contiene lógica económica, econométrica ni de presentación.
    """

    _SCHEMA_VERSION = 1
    _FILE_NAME = "latest_snapshot.json"

    def __init__(
        self,
        storage_path: Path | None = None,
    ) -> None:
        if storage_path is None:
            cache_root = Path(
                user_cache_dir(
                    appname="AIP Enterprise",
                    appauthor="Coopealianza",
                )
            )

            storage_path = cache_root / "economic" / self._FILE_NAME

        self._storage_path = Path(storage_path)

    @property
    def storage_path(self) -> Path:
        """Ruta física utilizada para persistencia."""
        return self._storage_path

    def exists(self) -> bool:
        """Indica si existe un snapshot persistido."""
        return self._storage_path.is_file()

    def save(
        self,
        snapshot: EconomicSnapshot,
    ) -> bool:
        """
        Persiste un snapshot válido mediante escritura atómica.

        Un snapshot no disponible no sustituye al último snapshot
        válido almacenado.
        """
        if not snapshot.available:
            logger.warning("Economic snapshot was not persisted because " "it is not available.")
            return False

        document = {
            "schema_version": self._SCHEMA_VERSION,
            "saved_at": (datetime.now(timezone.utc).isoformat()),
            "snapshot": asdict(snapshot),
        }

        serialized = JsonSerializer.serialize(document)

        directory = self._storage_path.parent

        temporary_path = self._storage_path.with_suffix(self._storage_path.suffix + ".tmp")

        try:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary_path.write_text(
                serialized,
                encoding="utf-8",
            )

            temporary_path.replace(self._storage_path)

        except OSError:
            logger.exception(
                "Unable to persist economic snapshot to %s",
                self._storage_path,
            )

            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Unable to remove temporary economic " "snapshot file %s",
                    temporary_path,
                )

            return False

        logger.info(
            "Economic snapshot persisted successfully: %s",
            self._storage_path,
        )

        return True

    def load(
        self,
    ) -> EconomicSnapshot | None:
        """
        Recupera el último snapshot persistido.

        Devuelve None cuando:
        - el archivo no existe;
        - el JSON está corrupto;
        - la versión es incompatible;
        - el contrato persistido no puede reconstruirse.
        """
        if not self.exists():
            return None

        try:
            raw_document = self._storage_path.read_text(encoding="utf-8")

            document = JsonSerializer.deserialize(raw_document)

            if not isinstance(
                document,
                dict,
            ):
                raise ValueError("Economic snapshot document " "must be an object.")

            schema_version = document.get("schema_version")

            if schema_version != self._SCHEMA_VERSION:
                logger.warning(
                    "Economic snapshot schema version " "is incompatible. Expected=%s Actual=%s",
                    self._SCHEMA_VERSION,
                    schema_version,
                )

                return None

            raw_snapshot = document.get("snapshot")

            if not isinstance(
                raw_snapshot,
                dict,
            ):
                raise ValueError("Economic snapshot payload " "is missing or invalid.")

            snapshot = self._deserialize_snapshot(raw_snapshot)

        except (
            OSError,
            ValueError,
            TypeError,
        ):
            logger.exception(
                "Unable to load persisted economic " "snapshot from %s",
                self._storage_path,
            )

            return None

        logger.info(
            "Economic snapshot loaded successfully: %s",
            self._storage_path,
        )

        return snapshot

    def delete(self) -> bool:
        """Elimina el snapshot persistido."""
        try:
            self._storage_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Unable to delete economic snapshot %s",
                self._storage_path,
            )

            return False

        return True

    @classmethod
    def _deserialize_snapshot(
        cls,
        payload: dict[str, Any],
    ) -> EconomicSnapshot:
        market_snapshot = tuple(
            cls._deserialize_card(item)
            for item in cls._as_dict_list(payload.get("market_snapshot"))
        )

        tri_crc_curve = tuple(
            cls._deserialize_curve_point(item)
            for item in cls._as_dict_list(payload.get("tri_crc_curve"))
        )

        tri_usd_curve = tuple(
            cls._deserialize_curve_point(item)
            for item in cls._as_dict_list(payload.get("tri_usd_curve"))
        )

        raw_diagnostics = payload.get(
            "diagnostics",
            [],
        )

        if not isinstance(
            raw_diagnostics,
            list,
        ):
            raw_diagnostics = []

        return EconomicSnapshot(
            status=str(
                payload.get(
                    "status",
                    "UNAVAILABLE",
                )
            ),
            source=str(
                payload.get(
                    "source",
                    "UNKNOWN",
                )
            ),
            cutoff_date=cls._as_date(payload.get("cutoff_date")),
            market_snapshot=(market_snapshot),
            tri_crc_curve=(tri_crc_curve),
            tri_usd_curve=(tri_usd_curve),
            diagnostics=tuple(str(item) for item in raw_diagnostics),
            cache_entries=cls._as_int(
                payload.get(
                    "cache_entries",
                    0,
                )
            ),
        )

    @classmethod
    def _deserialize_card(
        cls,
        payload: dict[str, Any],
    ) -> EconomicIndicatorCard:
        return EconomicIndicatorCard(
            code=str(
                payload.get(
                    "code",
                    "",
                )
            ),
            name=str(
                payload.get(
                    "name",
                    "",
                )
            ),
            value=cls._as_decimal(payload.get("value")),
            previous_value=(cls._as_decimal(payload.get("previous_value"))),
            absolute_change=(cls._as_decimal(payload.get("absolute_change"))),
            relative_change_percent=(cls._as_decimal(payload.get("relative_change_percent"))),
            trend=str(
                payload.get(
                    "trend",
                    "UNKNOWN",
                )
            ),
            observation_date=(cls._as_date(payload.get("observation_date"))),
            unit=str(
                payload.get(
                    "unit",
                    "",
                )
            ),
            source=str(
                payload.get(
                    "source",
                    "",
                )
            ),
            source_series_code=(cls._as_optional_string(payload.get("source_series_code"))),
            derived=bool(
                payload.get(
                    "derived",
                    False,
                )
            ),
            currency=(cls._as_optional_string(payload.get("currency"))),
            tenor=(cls._as_optional_string(payload.get("tenor"))),
        )

    @classmethod
    def _deserialize_curve_point(
        cls,
        payload: dict[str, Any],
    ) -> EconomicCurvePoint:
        return EconomicCurvePoint(
            code=str(
                payload.get(
                    "code",
                    "",
                )
            ),
            tenor=str(
                payload.get(
                    "tenor",
                    "",
                )
            ),
            value=cls._as_decimal(payload.get("value")),
            previous_value=(cls._as_decimal(payload.get("previous_value"))),
            absolute_change=(cls._as_decimal(payload.get("absolute_change"))),
            trend=str(
                payload.get(
                    "trend",
                    "UNKNOWN",
                )
            ),
            observation_date=(cls._as_date(payload.get("observation_date"))),
            source_series_code=(cls._as_optional_string(payload.get("source_series_code"))),
        )

    @staticmethod
    def _as_dict_list(
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            value,
            list,
        ):
            return []

        return [
            item
            for item in value
            if isinstance(
                item,
                dict,
            )
        ]

    @staticmethod
    def _as_decimal(
        value: Any,
    ) -> Decimal | None:
        if value is None:
            return None

        if isinstance(
            value,
            Decimal,
        ):
            return value

        try:
            return Decimal(str(value))
        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):
            return None

    @staticmethod
    def _as_date(
        value: Any,
    ) -> date | None:
        if value is None:
            return None

        if isinstance(
            value,
            date,
        ):
            return value

        if not isinstance(
            value,
            str,
        ):
            return None

        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _as_optional_string(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip()

        return normalized if normalized else None

    @staticmethod
    def _as_int(
        value: Any,
    ) -> int:
        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0
