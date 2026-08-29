from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from aip.domain.portfolio.risk.historical_price_series_service import (
    HistoricalPriceSeriesService,
)
from aip.domain.portfolio.risk.portfolio_historical_var_service import (
    PortfolioHistoricalVaRResult,
    PortfolioHistoricalVaRService,
    PortfolioVaRPosition,
)
from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.repositories.master_historical_price_repository import (
    MasterHistoricalPriceRepository,
)
from aip.product.configured.repositories.pipca_historical_price_repository import (
    PiPCAHistoricalPriceRepository,
)
from aip.product.demo.configuration.demo_config import DemoConfig


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioVaRExcludedTitle:
    """
    Título elegible para VER que no pudo incorporarse al cálculo
    por una razón técnica o por ausencia de información histórica.
    """

    isin: str
    series: str
    issuer: str
    currency: str
    maturity_date: date | None
    market_value_crc: Decimal
    reason: str
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioVaRPolicyExclusion:
    """
    Posición excluida del universo VER por una regla metodológica.
    """

    isin: str
    series: str
    issuer: str
    currency: str
    product_code: str
    classification: str
    market_value_crc: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class ConfiguredPortfolioVaRResult:
    """
    Resultado institucional completo del proceso VER.

    Se distinguen explícitamente:

    - portafolio total;
    - universo elegible para VER;
    - exclusiones metodológicas;
    - cobertura histórica;
    - títulos calculados;
    - títulos excluidos por ausencia de historia;
    - resultado VER consolidado.
    """

    valuation_date: date

    # ============================================================
    # POSITIONS
    # ============================================================

    source_position_count: int
    eligible_position_count: int
    policy_excluded_position_count: int

    grouped_title_count: int
    calculated_title_count: int
    excluded_title_count: int

    # ============================================================
    # MARKET VALUE
    # ============================================================

    source_market_value_crc: Decimal

    eligible_market_value_crc: Decimal
    policy_excluded_market_value_crc: Decimal

    calculated_market_value_crc: Decimal
    excluded_market_value_crc: Decimal

    # Cobertura histórica sobre el universo elegible para VER.
    coverage_percent: Decimal

    # ============================================================
    # HISTORICAL WINDOW
    # ============================================================

    vector_dates_available: int

    window_start_date: date | None
    window_end_date: date | None

    required_prices: int
    scenario_count: int
    horizon_observations: int

    # ============================================================
    # VER RESULT
    # ============================================================

    portfolio_var: PortfolioHistoricalVaRResult | None

    excluded_titles: tuple[
        ConfiguredPortfolioVaRExcludedTitle,
        ...,
    ]

    policy_exclusions: tuple[
        ConfiguredPortfolioVaRPolicyExclusion,
        ...,
    ]

    status: str
    diagnostic: str | None = None


@dataclass(slots=True)
class _GroupedTitle:
    """
    Agrupación interna de posiciones por título valor.

    ISIN constituye la llave preferente.

    Cuando no existe ISIN se utiliza:
        serie + emisor + vencimiento.
    """

    security_key: str

    isin: str
    series: str
    issuer: str
    currency: str
    product_code: str

    maturity_date: date | None

    market_value_crc: Decimal
    quantity_participations: Decimal

    position_count: int


class ConfiguredPortfolioVaRService:
    """
    Orquestador institucional del VER para CONFIGURED mode.

    ==============================================================
    UNIVERSO VER
    ==============================================================

    El universo se determina antes de consultar las fuentes
    históricas.

    Se excluyen:

    1. posiciones cuya clasificación inicia con "C.A";
    2. operaciones cuyo product_code es "MIL";
    3. posiciones con valor de mercado no positivo.

    El resto constituye el universo sujeto a VER.

    ==============================================================
    FUENTES HISTÓRICAS
    ==============================================================

    Fuente primaria:
        PiPCAHistoricalPriceRepository

    Fuente alternativa:
        MasterHistoricalPriceRepository

    Jerarquía:

        PiPCA
          |
          +-- existe historia -> utilizar PiPCA
          |
          +-- no existe historia
                   |
                   v
             Maestro histórico
                   |
                   +-- matching por ISIN preferentemente
                   +-- fallback por serie/emisor

    ==============================================================
    SERIE NORMALIZADA
    ==============================================================

    Todas las series se normalizan posteriormente mediante
    HistoricalPriceSeriesService.

    Regla institucional:

    - exactamente 521 precios;
    - misma ventana temporal;
    - si un título nuevo no dispone de suficientes observaciones,
      las faltantes se completan con su precio inicial conforme
      a la metodología establecida.

    ==============================================================
    METODOLOGÍA VER
    ==============================================================

    - 521 precios;
    - rendimientos logarítmicos;
    - horizonte de 21 observaciones;
    - 500 escenarios;
    - simulación histórica;
    - nivel de confianza 95%;
    - percentil inferior 5%;
    - escenario 25 al ordenar 500 escenarios de peor a mejor.

    No contiene lógica de presentación.
    """

    REQUIRED_PRICES = 521

    HORIZON_OBSERVATIONS = 21

    REQUIRED_SCENARIOS = 500

    def __init__(
        self,
        config: DemoConfig,
        source_config: ConfiguredSourceConfig,
        portfolio_provider: ConfiguredPortfolioProvider,
        *,
        valuation_date_context: ValuationDateContext | None = None,
    ) -> None:

        self._config = config

        self._source_config = (
            source_config
        )

        self._portfolio_provider = (
            portfolio_provider
        )

        self._valuation_date_context = valuation_date_context

        # ========================================================
        # HISTORICAL SOURCES - LAZY INITIALIZATION
        # ========================================================
        #
        # Los repositorios historicos no deben resolverse durante
        # el bootstrap general de AIP Enterprise.
        #
        # La disponibilidad del filesystem historico es una
        # dependencia del calculo VER, no del arranque completo
        # de la aplicacion.
        #
        # Se inicializan bajo demanda cuando calculate() es
        # invocado por el modulo Riesgo de Precio.
        # ========================================================

        self._historical_repository: (
            PiPCAHistoricalPriceRepository | None
        ) = None

        self._master_historical_repository: (
            MasterHistoricalPriceRepository | None
        ) = None

        # ========================================================
        # VER RESULT CACHE
        # ========================================================
        #
        # Cache por fecha efectiva de valoración.
        #
        # Evita recalcular el mismo VER cuando:
        # - se vuelve a abrir Riesgo de Precio;
        # - la vista ejecuta refresh();
        # - otro consumidor solicita el mismo corte.
        #
        # La lógica matemática permanece en _calculate_uncached().
        # ========================================================

        self._result_cache: dict[
            date,
            ConfiguredPortfolioVaRResult,
        ] = {}

    # =============================================================
    # HISTORICAL REPOSITORY LIFECYCLE
    # =============================================================

    def _ensure_historical_repositories(
        self,
    ) -> None:
        """
        Inicializa bajo demanda las fuentes historicas del VER.

        Esta operacion se ejecuta solamente cuando el calculo de
        Riesgo de Precio requiere historia.

        El orden institucional se conserva:

        1. PiPCAHistoricalPriceRepository como fuente primaria.
        2. MasterHistoricalPriceRepository como fallback.

        No modifica ninguna regla matematica del VER.
        """

        if (
            self._historical_repository
            is not None
            and self._master_historical_repository
            is not None
        ):
            return

        investment_root = (
            self._resolve_investment_root()
        )

        self._historical_repository = (
            PiPCAHistoricalPriceRepository(
                investment_root
            )
        )

        self._master_historical_repository = (
            MasterHistoricalPriceRepository(
                investment_root
            )
        )

    # =============================================================
    # PUBLIC API
    # =============================================================

    def calculate(
        self,
        *,
        valuation_date: date | None = None,
        force_refresh: bool = False,
    ) -> ConfiguredPortfolioVaRResult:
        """
        Devuelve el VER institucional para el corte solicitado.

        El resultado completo se conserva en memoria por fecha de
        valoración para evitar repetir la carga histórica y las
        simulaciones cuando el mismo corte vuelve a solicitarse.

        Parameters
        ----------
        valuation_date:
            Fecha explícita de valoración. Si es None se resuelve
            desde el portafolio/configuración vigente.

        force_refresh:
            Cuando es True ignora el cache y recalcula el corte.
            Se mantiene False por defecto para navegación normal.
        """

        # --------------------------------------------------------
        # Resolver fecha efectiva sin inicializar todavía los
        # repositorios históricos.
        # --------------------------------------------------------

        if valuation_date is not None:
            effective_date = valuation_date

        else:
            portfolio = (
                self._portfolio_provider
                .get_portfolio()
            )

            effective_date = (
                self._resolve_valuation_date(
                    portfolio
                )
            )

        # --------------------------------------------------------
        # CACHE HIT
        # --------------------------------------------------------

        if not force_refresh:
            cached = (
                self._result_cache.get(
                    effective_date
                )
            )

            if cached is not None:
                return cached

        # --------------------------------------------------------
        # CACHE MISS
        # --------------------------------------------------------

        result = (
            self._calculate_uncached(
                valuation_date=effective_date
            )
        )

        self._result_cache[
            effective_date
        ] = result

        return result

    def clear_result_cache(
        self,
        *,
        valuation_date: date | None = None,
    ) -> None:
        """
        Invalida resultados VER almacenados en memoria.

        Si se indica valuation_date elimina únicamente ese corte.
        Si es None elimina todos los cortes de la instancia.
        """

        if valuation_date is None:
            self._result_cache.clear()
            return

        self._result_cache.pop(
            valuation_date,
            None,
        )

    def cached_valuation_dates(
        self,
    ) -> tuple[date, ...]:
        """
        Devuelve las fechas actualmente disponibles en cache.
        """

        return tuple(
            sorted(
                self._result_cache
            )
        )

    def _calculate_uncached(
        self,
        *,
        valuation_date: date | None = None,
    ) -> ConfiguredPortfolioVaRResult:
        """
        Calcula el VER para el portafolio del corte vigente.

        La fecha efectiva corresponde al corte seleccionado
        en AIP Enterprise.

        El provider ya debe estar configurado para dicha fecha.
        """

        # ========================================================
        # HISTORICAL SOURCES
        # ========================================================

        self._ensure_historical_repositories()

        # ========================================================
        # CURRENT PORTFOLIO
        # ========================================================

        portfolio = (
            self._portfolio_provider
            .get_portfolio()
        )

        positions = [
            position
            for position in portfolio.get(
                "positions",
                [],
            )
            if isinstance(
                position,
                dict,
            )
        ]

        effective_date = (
            valuation_date
            or self._resolve_valuation_date(
                portfolio
            )
        )

        # ========================================================
        # TOTAL PORTFOLIO MARKET VALUE
        # ========================================================

        source_market_value_crc = sum(
            (
                self._position_market_value(
                    position
                )
                for position
                in positions
            ),
            Decimal("0"),
        )

        # ========================================================
        # VER ELIGIBILITY
        # ========================================================

        eligible_positions: list[
            dict[str, Any]
        ] = []

        policy_exclusions: list[
            ConfiguredPortfolioVaRPolicyExclusion
        ] = []

        for position in positions:

            market_value_crc = (
                self._position_market_value(
                    position
                )
            )

            exclusion_reason = (
                self._policy_exclusion_reason(
                    position
                )
            )

            if exclusion_reason is not None:

                policy_exclusions.append(
                    self._build_policy_exclusion(
                        position=position,
                        market_value_crc=(
                            market_value_crc
                        ),
                        reason=(
                            exclusion_reason
                        ),
                    )
                )

                continue

            if market_value_crc <= 0:

                policy_exclusions.append(
                    self._build_policy_exclusion(
                        position=position,
                        market_value_crc=(
                            market_value_crc
                        ),
                        reason=(
                            "NON_POSITIVE_MARKET_VALUE"
                        ),
                    )
                )

                continue

            eligible_positions.append(
                position
            )

        eligible_market_value_crc = sum(
            (
                self._position_market_value(
                    position
                )
                for position
                in eligible_positions
            ),
            Decimal("0"),
        )

        policy_excluded_market_value_crc = sum(
            (
                exclusion.market_value_crc
                for exclusion
                in policy_exclusions
            ),
            Decimal("0"),
        )

        # ========================================================
        # GROUP ELIGIBLE POSITIONS BY SECURITY
        # ========================================================

        grouped_titles = (
            self._group_positions(
                eligible_positions
            )
        )

        # ========================================================
        # COMMON PiPCA MARKET CALENDAR
        #
        # PiPCA dates continue to define the common 521-date
        # historical market window.
        # ========================================================

        available_dates = (
            self._historical_repository
            .available_vector_dates(
                cutoff_date=(
                    effective_date
                )
            )
        )

        if (
            len(available_dates)
            < self.REQUIRED_PRICES
        ):

            return ConfiguredPortfolioVaRResult(
                valuation_date=(
                    effective_date
                ),

                source_position_count=len(
                    positions
                ),

                eligible_position_count=len(
                    eligible_positions
                ),

                policy_excluded_position_count=len(
                    policy_exclusions
                ),

                grouped_title_count=len(
                    grouped_titles
                ),

                calculated_title_count=0,

                excluded_title_count=0,

                source_market_value_crc=(
                    source_market_value_crc
                ),

                eligible_market_value_crc=(
                    eligible_market_value_crc
                ),

                policy_excluded_market_value_crc=(
                    policy_excluded_market_value_crc
                ),

                calculated_market_value_crc=(
                    Decimal("0")
                ),

                excluded_market_value_crc=(
                    eligible_market_value_crc
                ),

                coverage_percent=(
                    Decimal("0")
                ),

                vector_dates_available=len(
                    available_dates
                ),

                window_start_date=None,

                window_end_date=None,

                required_prices=(
                    self.REQUIRED_PRICES
                ),

                scenario_count=0,

                horizon_observations=(
                    self.HORIZON_OBSERVATIONS
                ),

                portfolio_var=None,

                excluded_titles=(),

                policy_exclusions=tuple(
                    policy_exclusions
                ),

                status=(
                    "INSUFFICIENT_MARKET_HISTORY"
                ),

                diagnostic=(
                    "PiPCA history contains "
                    f"{len(available_dates)} dates; "
                    f"{self.REQUIRED_PRICES} are required"
                ),
            )

        target_dates = tuple(
            available_dates[
                -self.REQUIRED_PRICES:
            ]
        )

        # ========================================================
        # HISTORICAL SERIES
        # ========================================================

        var_positions: list[
            PortfolioVaRPosition
        ] = []

        excluded_titles: list[
            ConfiguredPortfolioVaRExcludedTitle
        ] = []

        for title in grouped_titles:

            # ----------------------------------------------------
            # DEFENSIVE MARKET VALUE CONTROL
            # ----------------------------------------------------

            if (
                title.market_value_crc
                <= 0
            ):

                excluded_titles.append(
                    ConfiguredPortfolioVaRExcludedTitle(
                        isin=(
                            title.isin
                        ),
                        series=(
                            title.series
                        ),
                        issuer=(
                            title.issuer
                        ),
                        currency=(
                            title.currency
                        ),
                        maturity_date=(
                            title.maturity_date
                        ),
                        market_value_crc=(
                            title.market_value_crc
                        ),
                        reason=(
                            "NON_POSITIVE_MARKET_VALUE"
                        ),
                    )
                )

                continue

            # ----------------------------------------------------
            # SECURITY IDENTIFICATION
            #
            # A security can still be valid with ISIN even if it
            # has no useful series.
            # ----------------------------------------------------

            if (
                not title.isin
                and not title.series
            ):

                excluded_titles.append(
                    ConfiguredPortfolioVaRExcludedTitle(
                        isin=(
                            title.isin
                        ),
                        series=(
                            title.series
                        ),
                        issuer=(
                            title.issuer
                        ),
                        currency=(
                            title.currency
                        ),
                        maturity_date=(
                            title.maturity_date
                        ),
                        market_value_crc=(
                            title.market_value_crc
                        ),
                        reason=(
                            "SECURITY_IDENTIFIER_UNAVAILABLE"
                        ),
                    )
                )

                continue

            # ====================================================
            # SOURCE 1: PiPCA
            # ====================================================

            pipca_history = (
                self._historical_repository
                .get_observations(
                    series=(
                        title.series
                    ),
                    issuer=(
                        title.issuer
                    ),
                    product_code=(
                        title.product_code
                    ),
                    maturity_date=(
                        title.maturity_date
                    ),
                    cutoff_date=(
                        effective_date
                    ),
                    limit=(
                        self.REQUIRED_PRICES
                    ),
                )
            )

            historical_observations = list(
                pipca_history.observations
            )

            historical_source = (
                "PIPCA"
            )

            historical_diagnostic = (
                pipca_history.diagnostic
            )

            # ====================================================
            # SOURCE 2: MASTER HISTORICAL FALLBACK
            #
            # Only invoked when PiPCA provides no observations.
            # ====================================================

            if (
                not historical_observations
            ):

                master_history = (
                    self._master_historical_repository
                    .get_observations(
                        isin=(
                            title.isin
                        ),
                        series=(
                            title.series
                        ),
                        issuer=(
                            title.issuer
                        ),
                        cutoff_date=(
                            effective_date
                        ),
                        limit=(
                            self.REQUIRED_PRICES
                        ),
                    )
                )

                historical_observations = list(
                    master_history.observations
                )

                historical_source = (
                    "MASTER"
                )

                historical_diagnostic = (
                    master_history.diagnostic
                )

            # ====================================================
            # HISTORY UNAVAILABLE IN BOTH SOURCES
            # ====================================================

            if (
                not historical_observations
            ):

                excluded_titles.append(
                    ConfiguredPortfolioVaRExcludedTitle(
                        isin=(
                            title.isin
                        ),
                        series=(
                            title.series
                        ),
                        issuer=(
                            title.issuer
                        ),
                        currency=(
                            title.currency
                        ),
                        maturity_date=(
                            title.maturity_date
                        ),
                        market_value_crc=(
                            title.market_value_crc
                        ),
                        reason=(
                            "MARKET_HISTORY_UNAVAILABLE"
                        ),
                        diagnostic=(
                            historical_diagnostic
                        ),
                    )
                )

                continue

            # ====================================================
            # CURRENT MARKET VALUE FOR VER
            # ====================================================
            #
            # Institutional reconciliation rule:
            #
            # For non-maturity investment-fund instruments in CRC,
            # when PiPCA provides a valid market price at the
            # valuation date and the portfolio provides quantity
            # of participations, the current VER exposure is:
            #
            #     quantity participations
            #     x PiPCA market price at valuation date
            #
            # Example validated against the approved risk tool:
            #
            #     PRSFI / fiprc
            #     981,800 x 1,007.09
            #     = CRC 988,760,962
            #
            # For every other instrument, the existing portfolio
            # market value remains unchanged.
            # ====================================================

            effective_market_value_crc = (
                title.market_value_crc
            )

            normalized_currency = (
                title.currency
                .strip()
                .upper()
            )

            is_crc_currency = (
                normalized_currency
                in {
                    "CRC",
                    "COLON",
                    "COLONES",
                }
            )

            if (
                title.maturity_date is None
                and title.quantity_participations > 0
                and is_crc_currency
                and historical_source == "PIPCA"
            ):

                cutoff_price = next(
                    (
                        observation.market_price
                        for observation
                        in reversed(
                            historical_observations
                        )
                        if (
                            observation.valuation_date
                            == effective_date
                            and observation.market_price > 0
                        )
                    ),
                    None,
                )

                if cutoff_price is not None:

                    effective_market_value_crc = (
                        title.quantity_participations
                        * cutoff_price
                    )

            # ====================================================
            # NORMALIZE TO COMMON 521-DATE WINDOW
            # ====================================================

            try:

                price_series = (
                    HistoricalPriceSeriesService
                    .build(
                        security_key=(
                            title.security_key
                        ),
                        observations=(
                            historical_observations
                        ),
                        valuation_date=(
                            effective_date
                        ),
                        target_dates=(
                            target_dates
                        ),
                    )
                )

            except (
                TypeError,
                ValueError,
            ) as exc:

                excluded_titles.append(
                    ConfiguredPortfolioVaRExcludedTitle(
                        isin=(
                            title.isin
                        ),
                        series=(
                            title.series
                        ),
                        issuer=(
                            title.issuer
                        ),
                        currency=(
                            title.currency
                        ),
                        maturity_date=(
                            title.maturity_date
                        ),
                        market_value_crc=(
                            title.market_value_crc
                        ),
                        reason=(
                            "HISTORICAL_SERIES_ERROR"
                        ),
                        diagnostic=(
                            f"{historical_source}: "
                            f"{exc}"
                        ),
                    )
                )

                continue

            # ====================================================
            # VER DOMAIN INPUT
            # ====================================================

            var_positions.append(
                PortfolioVaRPosition(
                    security_key=(
                        title.security_key
                    ),
                    series=(
                        title.series
                    ),
                    issuer=(
                        title.issuer
                    ),
                    currency=(
                        title.currency
                    ),
                    market_value_crc=(
                        effective_market_value_crc
                    ),
                    price_series=(
                        price_series
                    ),
                )
            )

        # ========================================================
        # HISTORICAL COVERAGE
        #
        # Denominator:
        #     VER eligible market value.
        #
        # NOT total portfolio market value.
        # ========================================================

        calculated_market_value_crc = sum(
            (
                position.market_value_crc
                for position
                in var_positions
            ),
            Decimal("0"),
        )

        excluded_market_value_crc = sum(
            (
                title.market_value_crc
                for title
                in excluded_titles
            ),
            Decimal("0"),
        )

        # ========================================================
        # HISTORICAL COVERAGE
        # ========================================================
        #
        # Coverage measures how much of the ORIGINAL VER-eligible
        # portfolio universe obtained usable historical information.
        #
        # It must not use the effective market value subsequently
        # adjusted by VER valuation rules (for example, quantity
        # participations x PiPCA cutoff price), because that value is
        # an exposure input to the risk calculation and not additional
        # historical coverage.
        #
        # Therefore:
        #
        #   covered source VM =
        #       eligible source VM
        #       - technically excluded source VM
        #
        # This guarantees that coverage remains in the 0%-100% range.
        # ========================================================

        covered_source_market_value_crc = max(
            Decimal("0"),
            (
                eligible_market_value_crc
                - excluded_market_value_crc
            ),
        )

        coverage_percent = (
            (
                covered_source_market_value_crc
                / eligible_market_value_crc
                * Decimal("100")
            )
            if (
                eligible_market_value_crc
                > 0
            )
            else Decimal("0")
        )

        coverage_percent = min(
            Decimal("100"),
            max(
                Decimal("0"),
                coverage_percent,
            ),
        )

        # ========================================================
        # NO CALCULABLE SECURITIES
        # ========================================================

        if not var_positions:

            return ConfiguredPortfolioVaRResult(
                valuation_date=(
                    effective_date
                ),

                source_position_count=len(
                    positions
                ),

                eligible_position_count=len(
                    eligible_positions
                ),

                policy_excluded_position_count=len(
                    policy_exclusions
                ),

                grouped_title_count=len(
                    grouped_titles
                ),

                calculated_title_count=0,

                excluded_title_count=len(
                    excluded_titles
                ),

                source_market_value_crc=(
                    source_market_value_crc
                ),

                eligible_market_value_crc=(
                    eligible_market_value_crc
                ),

                policy_excluded_market_value_crc=(
                    policy_excluded_market_value_crc
                ),

                calculated_market_value_crc=(
                    Decimal("0")
                ),

                excluded_market_value_crc=(
                    excluded_market_value_crc
                ),

                coverage_percent=(
                    Decimal("0")
                ),

                vector_dates_available=len(
                    available_dates
                ),

                window_start_date=(
                    target_dates[0]
                ),

                window_end_date=(
                    target_dates[-1]
                ),

                required_prices=(
                    self.REQUIRED_PRICES
                ),

                scenario_count=0,

                horizon_observations=(
                    self.HORIZON_OBSERVATIONS
                ),

                portfolio_var=None,

                excluded_titles=tuple(
                    excluded_titles
                ),

                policy_exclusions=tuple(
                    policy_exclusions
                ),

                status=(
                    "NO_ELIGIBLE_TITLES_WITH_HISTORY"
                ),

                diagnostic=(
                    "No VER-eligible title could "
                    "be incorporated into the "
                    "historical calculation"
                ),
            )

        # ========================================================
        # CONSOLIDATED HISTORICAL VER
        # ========================================================

        portfolio_var = (
            PortfolioHistoricalVaRService
            .calculate(
                positions=tuple(
                    var_positions
                )
            )
        )

        # ========================================================
        # STATUS
        # ========================================================

        if (
            len(excluded_titles)
            == 0
        ):

            status = (
                "CALCULATED"
            )

        elif (
            coverage_percent
            >= Decimal("99.5")
        ):

            status = (
                "CALCULATED_WITH_MINOR_HISTORY_EXCLUSIONS"
            )

        else:

            status = (
                "PARTIAL_HISTORY_COVERAGE"
            )

        # ========================================================
        # RESULT
        # ========================================================

        return ConfiguredPortfolioVaRResult(
            valuation_date=(
                effective_date
            ),

            source_position_count=len(
                positions
            ),

            eligible_position_count=len(
                eligible_positions
            ),

            policy_excluded_position_count=len(
                policy_exclusions
            ),

            grouped_title_count=len(
                grouped_titles
            ),

            calculated_title_count=len(
                var_positions
            ),

            excluded_title_count=len(
                excluded_titles
            ),

            source_market_value_crc=(
                source_market_value_crc
            ),

            eligible_market_value_crc=(
                eligible_market_value_crc
            ),

            policy_excluded_market_value_crc=(
                policy_excluded_market_value_crc
            ),

            calculated_market_value_crc=(
                calculated_market_value_crc
            ),

            excluded_market_value_crc=(
                excluded_market_value_crc
            ),

            coverage_percent=(
                coverage_percent
            ),

            vector_dates_available=len(
                available_dates
            ),

            window_start_date=(
                target_dates[0]
            ),

            window_end_date=(
                target_dates[-1]
            ),

            required_prices=(
                self.REQUIRED_PRICES
            ),

            scenario_count=(
                portfolio_var
                .scenario_count
            ),

            horizon_observations=(
                self.HORIZON_OBSERVATIONS
            ),

            portfolio_var=(
                portfolio_var
            ),

            excluded_titles=tuple(
                excluded_titles
            ),

            policy_exclusions=tuple(
                policy_exclusions
            ),

            status=status,

            diagnostic=None,
        )

    # =============================================================
    # POLICY / ELIGIBILITY
    # =============================================================

    @classmethod
    def _policy_exclusion_reason(
        cls,
        position: dict[
            str,
            Any,
        ],
    ) -> str | None:
        """
        Determina si una posición debe quedar fuera del universo VER.

        Regla institucional reconciliada:

        1. classification inicia con "C.A"
           -> COST_AMORTIZED

        2. product_code == "MIL"
           -> MIL_OPERATION

        El resto permanece elegible, sujeto a VM > 0.
        """

        classification = str(
            position.get(
                "classification"
            )
            or ""
        ).strip().upper()

        product_code = str(
            position.get(
                "product_code"
            )
            or ""
        ).strip().upper()

        if classification.startswith(
            "C.A"
        ):
            return (
                "COST_AMORTIZED"
            )

        if (
            product_code
            == "MIL"
        ):
            return (
                "MIL_OPERATION"
            )

        return None

    @classmethod
    def _build_policy_exclusion(
        cls,
        *,
        position: dict[
            str,
            Any,
        ],
        market_value_crc: Decimal,
        reason: str,
    ) -> ConfiguredPortfolioVaRPolicyExclusion:

        return ConfiguredPortfolioVaRPolicyExclusion(
            isin=str(
                position.get(
                    "isin"
                )
                or ""
            ).strip(),

            series=str(
                position.get(
                    "series"
                )
                or ""
            ).strip(),

            issuer=str(
                position.get(
                    "issuer"
                )
                or ""
            ).strip(),

            currency=str(
                position.get(
                    "currency"
                )
                or ""
            ).strip(),

            product_code=str(
                position.get(
                    "product_code"
                )
                or ""
            ).strip(),

            classification=str(
                position.get(
                    "classification"
                )
                or ""
            ).strip(),

            market_value_crc=(
                market_value_crc
            ),

            reason=(
                reason
            ),
        )

    # =============================================================
    # GROUPING
    # =============================================================

    def _group_positions(
        self,
        positions: list[
            dict[str, Any]
        ],
    ) -> tuple[
        _GroupedTitle,
        ...,
    ]:
        """
        Agrupa posiciones del mismo título.

        Jerarquía de identificación:

        1. ISIN.
        2. Si no hay ISIN:
           serie + emisor + vencimiento.

        Esto evita agrupar incorrectamente instrumentos diferentes
        que comparten una serie descriptiva, particularmente fondos.

        El valor de mercado se suma cuando el mismo título aparece
        en varios contratos o custodios.
        """

        grouped: dict[
            str,
            _GroupedTitle,
        ] = {}

        for position in positions:

            isin = str(
                position.get(
                    "isin"
                )
                or ""
            ).strip()

            series = str(
                position.get(
                    "series"
                )
                or position.get(
                    "series_or_security_code"
                )
                or ""
            ).strip()

            issuer = str(
                position.get(
                    "issuer"
                )
                or ""
            ).strip()

            currency = str(
                position.get(
                    "currency"
                )
                or ""
            ).strip()

            product_code = str(
                position.get(
                    "product_code"
                )
                or ""
            ).strip()

            maturity_date = (
                self._as_date(
                    position.get(
                        "maturity_date"
                    )
                    or position.get(
                        "maturity_date_if_present"
                    )
                )
            )

            market_value_crc = (
                self._position_market_value(
                    position
                )
            )

            source_values = (
                position.get(
                    "source_values"
                )
                or {}
            )

            quantity_participations = (
                self._decimal_value(
                    source_values.get(
                        "cantidad participaciones"
                    )
                    or position.get(
                        "quantity"
                    )
                )
            )

            key = (
                self._title_key(
                    isin=isin,
                    series=series,
                    issuer=issuer,
                    maturity_date=(
                        maturity_date
                    ),
                )
            )

            existing = (
                grouped.get(
                    key
                )
            )

            if existing is None:

                grouped[
                    key
                ] = _GroupedTitle(
                    security_key=(
                        key
                    ),
                    isin=(
                        isin
                    ),
                    series=(
                        series
                    ),
                    issuer=(
                        issuer
                    ),
                    currency=(
                        currency
                    ),
                    product_code=(
                        product_code
                    ),
                    maturity_date=(
                        maturity_date
                    ),
                    market_value_crc=(
                        market_value_crc
                    ),
                    quantity_participations=(
                        quantity_participations
                    ),
                    position_count=1,
                )

            else:

                existing.market_value_crc += (
                    market_value_crc
                )

                existing.quantity_participations += (
                    quantity_participations
                )

                existing.position_count += 1

        return tuple(
            grouped.values()
        )

    # =============================================================
    # CONFIGURATION
    # =============================================================

    def _resolve_investment_root(
        self,
    ) -> Path:
        """
        Obtiene la raíz institucional configurada.

        MasterHistoricalPriceRepository y
        PiPCAHistoricalPriceRepository aceptan la raíz institucional
        y resuelven internamente la subcarpeta Inversiones.
        """

        configured_root = (
            self._source_config
            .folder_watch
            .portfolio_root
        )

        if not configured_root:

            raise RuntimeError(
                "Portfolio root is not configured; "
                "historical VER cannot be calculated"
            )

        return Path(
            configured_root
        )

    def _resolve_valuation_date(
        self,
        portfolio: dict[
            str,
            Any,
        ],
    ) -> date:
        """
        Resuelve la fecha efectiva del portafolio.
        """

        raw_value = (
            portfolio.get(
                "valuation_date"
            )
            or (
                self._valuation_date_context.value
                if self._valuation_date_context is not None
                else self._config.data_cutoff_date
            )
        )

        resolved = (
            self._as_date(
                raw_value
            )
        )

        if resolved is None:

            raise ValueError(
                "Portfolio valuation date "
                "could not be resolved"
            )

        return resolved

    # =============================================================
    # HELPERS
    # =============================================================

    @staticmethod
    def _title_key(
        *,
        isin: str,
        series: str,
        issuer: str,
        maturity_date: date | None,
    ) -> str:
        """
        Construye la llave única del título.

        ISIN tiene prioridad absoluta.
        """

        normalized_isin = (
            isin
            .strip()
            .casefold()
        )

        if normalized_isin:

            return (
                f"isin:{normalized_isin}"
            )

        maturity_text = (
            maturity_date.isoformat()
            if maturity_date is not None
            else ""
        )

        return (
            f"series:"
            f"{series.strip().casefold()}"
            f"|issuer:"
            f"{issuer.strip().casefold()}"
            f"|maturity:"
            f"{maturity_text}"
        )

    @classmethod
    def _position_market_value(
        cls,
        position: dict[
            str,
            Any,
        ],
    ) -> Decimal:
        """
        Retorna el valor de mercado colonizado.
        """

        return cls._decimal_value(
            position.get(
                "market_value_crc"
            )
            or position.get(
                "market_value"
            )
        )

    @staticmethod
    def _decimal_value(
        value: object,
    ) -> Decimal:
        """
        Convierte un valor numérico a Decimal.
        """

        if value is None:
            return Decimal(
                "0"
            )

        if isinstance(
            value,
            Decimal,
        ):
            return value

        try:

            return Decimal(
                str(
                    value
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            return Decimal(
                "0"
            )

    @staticmethod
    def _as_date(
        value: object,
    ) -> date | None:
        """
        Convierte valores soportados a date.
        """

        if value is None:
            return None

        if isinstance(
            value,
            datetime,
        ):
            return (
                value.date()
            )

        if isinstance(
            value,
            date,
        ):
            return value

        text = str(
            value
        ).strip()

        if not text:
            return None

        try:

            return date.fromisoformat(
                text[:10]
            )

        except ValueError:

            return None
