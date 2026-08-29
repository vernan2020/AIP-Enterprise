from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aip.product.configured.protocols import (
    EconomicIndicatorsProvider,
)


@dataclass(
    frozen=True,
    slots=True,
)
class EconomicIndicatorCard:
    """
    Modelo de presentación de un indicador económico.

    No contiene reglas de negocio ni lógica econométrica.
    Su responsabilidad es exponer información normalizada
    para la capa de interfaz.
    """

    code: str
    name: str
    value: Decimal | None
    previous_value: Decimal | None
    absolute_change: Decimal | None
    relative_change_percent: Decimal | None
    trend: str
    observation_date: date | None
    unit: str
    source: str
    source_series_code: str | None
    derived: bool
    currency: str | None = None
    tenor: str | None = None

    @property
    def available(self) -> bool:
        return self.value is not None


@dataclass(
    frozen=True,
    slots=True,
)
class EconomicCurvePoint:
    """Punto de una curva TRI preparado para presentación."""

    code: str
    tenor: str
    value: Decimal | None
    previous_value: Decimal | None
    absolute_change: Decimal | None
    trend: str
    observation_date: date | None
    source_series_code: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class EconomicSnapshot:
    """
    Snapshot completo de Macro Intelligence.

    Constituye el contrato entre la capa de datos económicos
    y la futura interfaz gráfica.
    """

    status: str
    source: str
    cutoff_date: date | None

    market_snapshot: tuple[
        EconomicIndicatorCard,
        ...,
    ]

    tri_crc_curve: tuple[
        EconomicCurvePoint,
        ...,
    ]

    tri_usd_curve: tuple[
        EconomicCurvePoint,
        ...,
    ]

    diagnostics: tuple[str, ...]

    cache_entries: int

    @property
    def available(self) -> bool:
        return (
            self.status == "AVAILABLE"
            and bool(self.market_snapshot)
        )


class EconomicViewModel:
    """
    ViewModel del módulo Macro Intelligence.

    Responsabilidades:
    - consumir EconomicIndicatorsProvider;
    - normalizar el payload para presentación;
    - construir el snapshot macroeconómico;
    - exponer curvas TRI CRC y USD;
    - determinar fecha de corte;
    - preservar diagnósticos de integración.

    No realiza:
    - forecasting;
    - correlaciones;
    - econometría;
    - simulación de escenarios;
    - cálculo de impacto institucional.
    """

    _SNAPSHOT_ORDER = (
        "FX_SELL",
        "INFLATION",
        "TPM",
        "TBP",
        "IMAE",
        "GDP",
        "UNEMPLOYMENT",
    )

    def __init__(
        self,
        provider: EconomicIndicatorsProvider,
    ) -> None:
        self._provider = provider

    def load(self) -> EconomicSnapshot:
        """
        Obtiene y transforma el estado macroeconómico actual.
        """

        payload = (
            self._provider.get_indicators()
        )

        status = str(
            payload.get(
                "status",
                "UNAVAILABLE",
            )
        )

        source = str(
            payload.get(
                "source",
                "UNKNOWN",
            )
        )

        raw_indicators = payload.get(
            "indicators",
            [],
        )

        indicators = (
            raw_indicators
            if isinstance(
                raw_indicators,
                list,
            )
            else []
        )

        indicator_map = {
            str(
                item.get(
                    "code",
                    "",
                )
            ): item
            for item in indicators
            if isinstance(
                item,
                dict,
            )
        }

        market_snapshot = tuple(
            self._build_card(
                indicator_map[code]
            )
            for code in self._SNAPSHOT_ORDER
            if code in indicator_map
        )

        raw_tri_curves = payload.get(
            "tri_curves",
            {},
        )

        tri_curves = (
            raw_tri_curves
            if isinstance(
                raw_tri_curves,
                dict,
            )
            else {}
        )

        tri_crc_curve = (
            self._build_curve(
                tri_curves.get(
                    "CRC",
                    [],
                )
            )
        )

        tri_usd_curve = (
            self._build_curve(
                tri_curves.get(
                    "USD",
                    [],
                )
            )
        )

        diagnostics = (
            self._build_diagnostics(
                payload
            )
        )

        cache_entries = (
            self._extract_cache_entries(
                payload
            )
        )

        cutoff_date = (
            self._determine_cutoff_date(
                market_snapshot,
                tri_crc_curve,
                tri_usd_curve,
            )
        )

        return EconomicSnapshot(
            status=status,
            source=source,
            cutoff_date=cutoff_date,
            market_snapshot=market_snapshot,
            tri_crc_curve=tri_crc_curve,
            tri_usd_curve=tri_usd_curve,
            diagnostics=diagnostics,
            cache_entries=cache_entries,
        )

    @staticmethod
    def _build_card(
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
            value=(
                EconomicViewModel
                ._as_decimal(
                    payload.get(
                        "value"
                    )
                )
            ),
            previous_value=(
                EconomicViewModel
                ._as_decimal(
                    payload.get(
                        "previous_value"
                    )
                )
            ),
            absolute_change=(
                EconomicViewModel
                ._as_decimal(
                    payload.get(
                        "absolute_change"
                    )
                )
            ),
            relative_change_percent=(
                EconomicViewModel
                ._as_decimal(
                    payload.get(
                        "relative_change_percent"
                    )
                )
            ),
            trend=str(
                payload.get(
                    "trend",
                    "UNKNOWN",
                )
            ),
            observation_date=(
                EconomicViewModel
                ._as_date(
                    payload.get(
                        "date"
                    )
                )
            ),
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
            source_series_code=(
                EconomicViewModel
                ._as_optional_string(
                    payload.get(
                        "source_series_code"
                    )
                )
            ),
            derived=bool(
                payload.get(
                    "derived",
                    False,
                )
            ),
            currency=(
                EconomicViewModel
                ._as_optional_string(
                    payload.get(
                        "currency"
                    )
                )
            ),
            tenor=(
                EconomicViewModel
                ._as_optional_string(
                    payload.get(
                        "tenor"
                    )
                )
            ),
        )

    @staticmethod
    def _build_curve(
        payload: Any,
    ) -> tuple[
        EconomicCurvePoint,
        ...,
    ]:
        if not isinstance(
            payload,
            list,
        ):
            return ()

        result: list[
            EconomicCurvePoint
        ] = []

        for item in payload:
            if not isinstance(
                item,
                dict,
            ):
                continue

            code = str(
                item.get(
                    "code",
                    "",
                )
            )

            tenor = str(
                item.get(
                    "tenor",
                    "",
                )
            )

            if (
                not code
                or not tenor
            ):
                continue

            result.append(
                EconomicCurvePoint(
                    code=code,
                    tenor=tenor,
                    value=(
                        EconomicViewModel
                        ._as_decimal(
                            item.get(
                                "value"
                            )
                        )
                    ),
                    previous_value=(
                        EconomicViewModel
                        ._as_decimal(
                            item.get(
                                "previous_value"
                            )
                        )
                    ),
                    absolute_change=(
                        EconomicViewModel
                        ._as_decimal(
                            item.get(
                                "absolute_change"
                            )
                        )
                    ),
                    trend=str(
                        item.get(
                            "trend",
                            "UNKNOWN",
                        )
                    ),
                    observation_date=(
                        EconomicViewModel
                        ._as_date(
                            item.get(
                                "date"
                            )
                        )
                    ),
                    source_series_code=(
                        EconomicViewModel
                        ._as_optional_string(
                            item.get(
                                "source_series_code"
                            )
                        )
                    ),
                )
            )

        return tuple(
            result
        )

    @staticmethod
    def _build_diagnostics(
        payload: dict[str, Any],
    ) -> tuple[str, ...]:
        raw_diagnostics = (
            payload.get(
                "diagnostics"
            )
        )

        if isinstance(
            raw_diagnostics,
            list,
        ):
            return tuple(
                str(item)
                for item
                in raw_diagnostics
            )

        diagnostic = payload.get(
            "diagnostic"
        )

        if diagnostic:
            return (
                str(diagnostic),
            )

        return ()

    @staticmethod
    def _extract_cache_entries(
        payload: dict[str, Any],
    ) -> int:
        cache = payload.get(
            "cache"
        )

        if not isinstance(
            cache,
            dict,
        ):
            return 0

        entries = cache.get(
            "entries",
            0,
        )

        try:
            return int(
                entries
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

    @staticmethod
    def _determine_cutoff_date(
        market_snapshot: tuple[
            EconomicIndicatorCard,
            ...,
        ],
        tri_crc_curve: tuple[
            EconomicCurvePoint,
            ...,
        ],
        tri_usd_curve: tuple[
            EconomicCurvePoint,
            ...,
        ],
    ) -> date | None:
        """
        Determina la fecha más reciente disponible.

        Importante:
        los indicadores económicos tienen frecuencias
        diferentes. Esta fecha representa la fecha de
        información más reciente del snapshot, no implica
        que todos los indicadores tengan el mismo corte.
        """

        dates: list[date] = []

        for indicator in market_snapshot:
            if (
                indicator.observation_date
                is not None
            ):
                dates.append(
                    indicator.observation_date
                )

        for point in (
            tri_crc_curve
            + tri_usd_curve
        ):
            if (
                point.observation_date
                is not None
            ):
                dates.append(
                    point.observation_date
                )

        if not dates:
            return None

        return max(
            dates
        )

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
            return Decimal(
                str(value)
            )

        except (
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

        if isinstance(
            value,
            str,
        ):
            try:
                return date.fromisoformat(
                    value
                )

            except ValueError:
                return None

        return None

    @staticmethod
    def _as_optional_string(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return (
            normalized
            if normalized
            else None
        )
