from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from aip.domain.economic.economic_indicator_catalog import (
    EconomicIndicatorFrequency,
    get_indicator_definition,
)
from aip.domain.economic.economic_indicator_observation import (
    EconomicIndicatorObservation,
)
from aip.domain.economic.economic_indicator_series import (
    EconomicIndicatorSeries,
)
from aip.integration.bccr.configuration.bccr_config import (
    BCCRConfig,
)
from aip.integration.bccr.connector.cache import (
    BCCRCache,
)
from aip.integration.bccr.connector.rest_client import (
    BCCRRestClient,
)
from aip.integration.bccr.normalization.economic_series_parser import (
    BCCREconomicSeriesParser,
)
from aip.integration.bccr.providers.urllib_http_provider import (
    UrllibHTTPProvider,
)
from aip.integration.economic.official_indicator_mappings import (
    build_official_indicator_mapper,
)
from aip.product.configured.protocols import (
    EconomicIndicatorsProvider,
)
from aip.product.configured.repositories.economic_historical_repository import (
    EconomicHistoricalRepository,
)


class ConfiguredEconomicIndicatorsProvider(EconomicIndicatorsProvider):
    """Provider configurado de indicadores económicos BCCR."""

    _FX_CHART_CODE = "1"
    _LABOR_CHART_CODE = "17"
    _TRI_CHART_CODE = "432"

    _FX_INDICATORS = (
        "FX_BUY",
        "FX_SELL",
    )

    _CORE_INDICATORS = (
        "TPM",
        "TBP",
        "INFLATION",
        "IMAE",
        "GDP",
    )

    _LABOR_INPUTS = (
        "LABOR_FORCE",
        "EMPLOYED",
    )

    _TTL_BY_CODE: dict[str, int] = {
        "TPM": 900,
        "TBP": 900,
        "INFLATION": 21600,
        "IMAE": 21600,
        "GDP": 86400,
    }

    _FX_TTL_SECONDS = 300
    _LABOR_TTL_SECONDS = 86400
    _TRI_TTL_SECONDS = 900

    def __init__(
        self,
        *,
        bccr_config: BCCRConfig,
    ) -> None:
        self._bccr_config = bccr_config

        self._client = BCCRRestClient(
            config=bccr_config,
            provider=UrllibHTTPProvider(),
        )

        self._mapper = build_official_indicator_mapper()

        self._parser = BCCREconomicSeriesParser(self._mapper)

        self._cache = BCCRCache(ttl_seconds=300)

    def get_indicators(
        self,
    ) -> dict[str, Any]:
        if not self._bccr_config.token:
            return self._historical_fallback(reason="BCCR token is unavailable")

        indicators: list[dict[str, Any]] = []

        diagnostics: list[str] = []

        observations_by_code: dict[
            str,
            tuple[
                EconomicIndicatorObservation,
                ...,
            ],
        ] = {}

        # ----------------------------------------------------
        # Foreign exchange
        #
        # BCCR Cuadro 1 returns both official USD/CRC
        # reference series in one request:
        #
        # 317 -> FX_BUY
        # 318 -> FX_SELL
        # ----------------------------------------------------

        try:
            fx_observations = self._get_or_fetch_grouped_chart_observations(
                chart_code=self._FX_CHART_CODE,
                logical_codes=self._FX_INDICATORS,
                history_days=45,
                ttl_seconds=self._FX_TTL_SECONDS,
            )

            for logical_code in self._FX_INDICATORS:
                observations = fx_observations.get(
                    logical_code,
                    (),
                )

                observations_by_code[logical_code] = observations

                if not observations:
                    diagnostics.append(f"{logical_code}: no observations")
                    continue

                indicator = self._build_indicator_payload(
                    logical_code,
                    observations,
                )

                if indicator is not None:
                    indicators.append(indicator)

        except (
            ConnectionError,
            TimeoutError,
            ValueError,
        ) as exc:
            diagnostics.append("FX: " f"{type(exc).__name__}: {exc}")

        # ----------------------------------------------------
        # Indicators that remain official standalone BCCR
        # series.
        # ----------------------------------------------------

        for logical_code in self._CORE_INDICATORS:
            try:
                observations = self._get_or_fetch_observations(logical_code)

                observations_by_code[logical_code] = observations

                if not observations:
                    diagnostics.append(f"{logical_code}: no observations")
                    continue

                indicator = self._build_indicator_payload(
                    logical_code,
                    observations,
                )

                if indicator is not None:
                    indicators.append(indicator)

            except (
                ConnectionError,
                TimeoutError,
                ValueError,
            ) as exc:
                diagnostics.append(f"{logical_code}: " f"{type(exc).__name__}: {exc}")

        # ----------------------------------------------------
        # Labor market
        #
        # BCCR Cuadro 17 returns both source series needed by
        # the unemployment-rate derivation:
        #
        # 22786 -> LABOR_FORCE
        # 22787 -> EMPLOYED
        # ----------------------------------------------------

        try:
            labor_observations = self._get_or_fetch_grouped_chart_observations(
                chart_code=self._LABOR_CHART_CODE,
                logical_codes=self._LABOR_INPUTS,
                history_days=400,
                ttl_seconds=self._LABOR_TTL_SECONDS,
            )

            for logical_code in self._LABOR_INPUTS:
                observations = labor_observations.get(
                    logical_code,
                    (),
                )

                observations_by_code[logical_code] = observations

                if not observations:
                    diagnostics.append(f"{logical_code}: no observations")
                    continue

                indicator = self._build_indicator_payload(
                    logical_code,
                    observations,
                )

                if indicator is not None:
                    indicators.append(indicator)

        except (
            ConnectionError,
            TimeoutError,
            ValueError,
        ) as exc:
            diagnostics.append("LABOR: " f"{type(exc).__name__}: {exc}")

        try:
            tri_observations = self._get_or_fetch_tri_observations()

            for logical_code, observations in tri_observations.items():
                observations_by_code[logical_code] = observations

                indicator = self._build_indicator_payload(
                    logical_code,
                    observations,
                )

                if indicator is not None:
                    indicators.append(indicator)

        except (
            ConnectionError,
            TimeoutError,
            ValueError,
        ) as exc:
            diagnostics.append("TRI: " f"{type(exc).__name__}: {exc}")

        unemployment = self._build_unemployment_indicator(observations_by_code)

        if unemployment is not None:
            indicators.append(unemployment)
        else:
            diagnostics.append("UNEMPLOYMENT: derived calculation unavailable")

        if not indicators:
            return self._historical_fallback(
                reason=("; ".join(diagnostics) if diagnostics else "BCCR live data unavailable")
            )

        return {
            "status": "AVAILABLE",
            "source": "BCCR",
            "indicators": indicators,
            "tri_curves": {
                "CRC": self._build_tri_curve(
                    indicators,
                    "CRC",
                ),
                "USD": self._build_tri_curve(
                    indicators,
                    "USD",
                ),
            },
            "diagnostics": diagnostics,
            "cache": {
                "entries": self._cache.size(),
            },
        }

    def _historical_fallback(
        self,
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Build a presentation-compatible payload from persisted history.

        This keeps Macro Intelligence operational during credential, network,
        rate-limit, or BCCR service interruptions without fabricating data.
        """
        repository = EconomicHistoricalRepository()
        requested_codes = (
            *self._FX_INDICATORS,
            *self._CORE_INDICATORS,
            "UNEMPLOYMENT",
        )

        indicators: list[dict[str, Any]] = []
        available_codes = set(repository.available_series())

        tri_codes = sorted(
            code
            for code in available_codes
            if code.startswith("TRI_CRC_") or code.startswith("TRI_USD_")
        )

        for logical_code in (*requested_codes, *tri_codes):
            if logical_code not in available_codes:
                continue

            series = repository.get_series(logical_code)
            if not series.observations:
                continue

            converted = tuple(
                EconomicIndicatorObservation(
                    indicator_code=item.indicator_code,
                    observation_date=item.observation_date,
                    value=item.value,
                    source=item.source,
                    unit=item.unit,
                    source_series_code=item.source_series_code,
                    quality_status="VALID",
                    is_preliminary=False,
                )
                for item in series.observations[-2:]
            )

            payload = self._build_indicator_payload(
                logical_code,
                converted,
            )
            if payload is not None:
                payload["source"] = series.source
                indicators.append(payload)

        return {
            "status": "AVAILABLE" if indicators else "UNAVAILABLE",
            "source": "BCCR · HISTÓRICO LOCAL",
            "indicators": indicators,
            "tri_curves": {
                "CRC": self._build_tri_curve(indicators, "CRC"),
                "USD": self._build_tri_curve(indicators, "USD"),
            },
            "diagnostics": (
                f"Live BCCR unavailable: {reason}",
                "Using persisted official economic history",
            ),
            "cache": {"entries": 0},
        }

    def _get_or_fetch_observations(
        self,
        logical_code: str,
    ) -> tuple[
        EconomicIndicatorObservation,
        ...,
    ]:
        cache_key = f"indicator:{logical_code}"

        cached = self._cache.get(cache_key)

        if isinstance(
            cached,
            tuple,
        ):
            return cached

        observations = self._fetch_observations(logical_code)

        ttl_seconds = self._TTL_BY_CODE.get(
            logical_code,
            300,
        )

        if observations:
            self._cache.set(
                cache_key,
                observations,
                ttl_seconds=ttl_seconds,
            )

        return observations

    def _get_or_fetch_grouped_chart_observations(
        self,
        *,
        chart_code: str,
        logical_codes: tuple[str, ...],
        history_days: int,
        ttl_seconds: int,
    ) -> dict[
        str,
        tuple[
            EconomicIndicatorObservation,
            ...,
        ],
    ]:
        """
        Return logical observations obtained from one
        consolidated BCCR chart request.

        The cache is maintained at chart level so one
        HTTP response supplies all logical indicators
        contained in the requested group.
        """

        cache_key = f"chart:{chart_code}"

        cached = self._cache.get(cache_key)

        if isinstance(
            cached,
            dict,
        ):
            return {
                logical_code: tuple(
                    cached.get(
                        logical_code,
                        (),
                    )
                )
                for logical_code in logical_codes
            }

        observations = self._fetch_grouped_chart_observations(
            chart_code=chart_code,
            logical_codes=logical_codes,
            history_days=history_days,
        )

        if observations:
            self._cache.set(
                cache_key,
                observations,
                ttl_seconds=ttl_seconds,
            )

        return observations

    def _fetch_grouped_chart_observations(
        self,
        *,
        chart_code: str,
        logical_codes: tuple[str, ...],
        history_days: int,
    ) -> dict[
        str,
        tuple[
            EconomicIndicatorObservation,
            ...,
        ],
    ]:
        """
        Fetch and parse a complete BCCR chart, retaining
        only the requested logical indicators.
        """

        if history_days <= 0:
            raise ValueError("history_days must be greater than zero")

        to_date = date.today()

        from_date = to_date - timedelta(days=history_days)

        response = self._client.fetch_chart_series(
            chart_code=chart_code,
            from_date=(from_date.strftime("%Y/%m/%d")),
            to_date=(to_date.strftime("%Y/%m/%d")),
        )

        body = response.get("body")

        if not isinstance(
            body,
            dict,
        ):
            return {}

        normalized_body = self._normalize_chart_payload(body)

        parsed = self._parser.parse(normalized_body)

        requested_codes = set(logical_codes)

        grouped: dict[
            str,
            list[EconomicIndicatorObservation],
        ] = {logical_code: [] for logical_code in logical_codes}

        for observation in parsed:
            logical_code = observation.indicator_code

            if logical_code not in requested_codes:
                continue

            grouped[logical_code].append(observation)

        return {
            logical_code: tuple(
                sorted(
                    items,
                    key=lambda item: (item.observation_date),
                )
            )
            for logical_code, items in grouped.items()
            if items
        }

    def _get_or_fetch_tri_observations(
        self,
    ) -> dict[
        str,
        tuple[
            EconomicIndicatorObservation,
            ...,
        ],
    ]:
        cache_key = f"chart:{self._TRI_CHART_CODE}"

        cached = self._cache.get(cache_key)

        if isinstance(
            cached,
            dict,
        ):
            return cached

        observations = self._fetch_tri_observations()

        if observations:
            self._cache.set(
                cache_key,
                observations,
                ttl_seconds=(self._TRI_TTL_SECONDS),
            )

        return observations

    def _fetch_observations(
        self,
        logical_code: str,
    ) -> tuple[
        EconomicIndicatorObservation,
        ...,
    ]:
        mapping = self._mapper.resolve(
            logical_code,
            "BCCR",
        )

        if mapping is None:
            return ()

        definition = get_indicator_definition(logical_code)

        if definition is None:
            return ()

        to_date = date.today()

        from_date = to_date - self._history_window(definition.frequency)

        response = self._client.fetch_series(
            indicator_code=(mapping.source_series_code),
            from_date=(from_date.strftime("%Y/%m/%d")),
            to_date=(to_date.strftime("%Y/%m/%d")),
        )

        body = response.get("body")

        if not isinstance(
            body,
            dict,
        ):
            return ()

        observations = self._parser.parse(body)

        return tuple(
            observation
            for observation in observations
            if (observation.indicator_code == logical_code)
        )

    def _fetch_tri_observations(
        self,
    ) -> dict[
        str,
        tuple[
            EconomicIndicatorObservation,
            ...,
        ],
    ]:
        to_date = date.today()

        from_date = to_date - timedelta(days=45)

        response = self._client.fetch_chart_series(
            chart_code=(self._TRI_CHART_CODE),
            from_date=(from_date.strftime("%Y/%m/%d")),
            to_date=(to_date.strftime("%Y/%m/%d")),
        )

        body = response.get("body")

        if not isinstance(
            body,
            dict,
        ):
            return {}

        normalized_body = self._normalize_chart_payload(body)

        observations = self._parser.parse(normalized_body)

        grouped: dict[
            str,
            list[EconomicIndicatorObservation],
        ] = {}

        for observation in observations:
            if not (
                observation.indicator_code.startswith("TRI_CRC_")
                or observation.indicator_code.startswith("TRI_USD_")
            ):
                continue

            grouped.setdefault(
                observation.indicator_code,
                [],
            ).append(observation)

        return {
            logical_code: tuple(
                sorted(
                    items,
                    key=lambda item: (item.observation_date),
                )
            )
            for logical_code, items in grouped.items()
        }

    @staticmethod
    def _normalize_chart_payload(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if payload.get("estado") is not True:
            raise ValueError(
                str(
                    payload.get(
                        "mensaje",
                        "BCCR chart response is not successful",
                    )
                )
            )

        raw_data = payload.get("datos")

        if not isinstance(
            raw_data,
            list,
        ):
            raise ValueError("BCCR chart payload does not contain datos list")

        indicators: list[dict[str, Any]] = []

        for chart in raw_data:
            if not isinstance(
                chart,
                dict,
            ):
                continue

            raw_indicators = chart.get(
                "indicadores",
                [],
            )

            if not isinstance(
                raw_indicators,
                list,
            ):
                continue

            for indicator in raw_indicators:
                if not isinstance(
                    indicator,
                    dict,
                ):
                    continue

                source_code = str(
                    indicator.get(
                        "codigoIndicador",
                        "",
                    )
                ).strip()

                if not source_code:
                    continue

                series = indicator.get(
                    "series",
                    [],
                )

                if not isinstance(
                    series,
                    list,
                ):
                    continue

                indicators.append(
                    {
                        "codigoIndicador": (source_code),
                        "nombreIndicador": (indicator.get("nombreIndicador")),
                        "series": series,
                    }
                )

        return {
            "estado": True,
            "mensaje": (
                payload.get(
                    "mensaje",
                    "Consulta exitosa",
                )
            ),
            "datos": indicators,
        }

    @staticmethod
    def _history_window(
        frequency: EconomicIndicatorFrequency,
    ) -> timedelta:
        if frequency == EconomicIndicatorFrequency.DAILY:
            return timedelta(days=45)

        if frequency == EconomicIndicatorFrequency.MONTHLY:
            return timedelta(days=450)

        if frequency == EconomicIndicatorFrequency.QUARTERLY:
            return timedelta(days=800)

        return timedelta(days=365)

    @staticmethod
    def _build_indicator_payload(
        logical_code: str,
        observations: tuple[
            EconomicIndicatorObservation,
            ...,
        ],
    ) -> dict[str, Any] | None:
        definition = get_indicator_definition(logical_code)

        if definition is None:
            return None

        series = EconomicIndicatorSeries(
            definition=definition,
            observations=observations,
        )

        latest = series.latest
        previous = series.previous

        if latest is None:
            return None

        return {
            "code": logical_code,
            "name": definition.name,
            "category": (definition.category.value),
            "frequency": (definition.frequency.value),
            "unit": definition.unit,
            "currency": definition.currency,
            "tenor": definition.tenor,
            "source": "BCCR",
            "derived": definition.derived,
            "source_series_code": (latest.source_series_code),
            "date": latest.observation_date,
            "value": latest.value,
            "previous_value": (previous.value if previous else None),
            "absolute_change": (series.absolute_change),
            "relative_change_percent": (series.relative_change_percent),
            "trend": series.trend,
            "observations": observations,
        }

    def _build_unemployment_indicator(
        self,
        observations_by_code: dict[
            str,
            tuple[
                EconomicIndicatorObservation,
                ...,
            ],
        ],
    ) -> dict[str, Any] | None:
        labor_force = observations_by_code.get(
            "LABOR_FORCE",
            (),
        )

        employed = observations_by_code.get(
            "EMPLOYED",
            (),
        )

        if not labor_force or not employed:
            return None

        labor_by_date = {item.observation_date: item for item in labor_force}

        employed_by_date = {item.observation_date: item for item in employed}

        common_dates = sorted(set(labor_by_date) & set(employed_by_date))

        derived_observations: list[EconomicIndicatorObservation] = []

        for observation_date in common_dates:
            labor_value = labor_by_date[observation_date].value

            employed_value = employed_by_date[observation_date].value

            if labor_value <= 0:
                continue

            unemployment_rate = (labor_value - employed_value) / labor_value * Decimal("100")

            derived_observations.append(
                EconomicIndicatorObservation(
                    indicator_code=("UNEMPLOYMENT"),
                    observation_date=(observation_date),
                    value=(unemployment_rate),
                    source="BCCR",
                    unit="%",
                    source_series_code=("DERIVED:22786-22787"),
                    quality_status="VALID",
                    is_preliminary=False,
                )
            )

        if not derived_observations:
            return None

        return self._build_indicator_payload(
            "UNEMPLOYMENT",
            tuple(derived_observations),
        )

    @staticmethod
    def _build_tri_curve(
        indicators: list[dict[str, Any]],
        currency: str,
    ) -> list[dict[str, Any]]:
        tenor_order = {
            "1W": 1,
            "1M": 2,
            "3M": 3,
            "6M": 4,
            "9M": 5,
            "12M": 6,
            "24M": 7,
            "36M": 8,
            "60M": 9,
        }

        curve = [
            {
                "code": indicator.get("code"),
                "tenor": indicator.get("tenor"),
                "value": indicator.get("value"),
                "previous_value": (indicator.get("previous_value")),
                "absolute_change": (indicator.get("absolute_change")),
                "trend": indicator.get("trend"),
                "date": indicator.get("date"),
                "source_series_code": (indicator.get("source_series_code")),
            }
            for indicator in indicators
            if (
                indicator.get("currency") == currency
                and str(
                    indicator.get(
                        "code",
                        "",
                    )
                ).startswith(f"TRI_{currency}_")
            )
        ]

        curve.sort(
            key=lambda item: (
                tenor_order.get(
                    str(
                        item.get(
                            "tenor",
                            "",
                        )
                    ),
                    999,
                )
            )
        )

        return curve
