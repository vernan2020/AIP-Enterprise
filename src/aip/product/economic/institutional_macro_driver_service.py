from __future__ import annotations

from collections import defaultdict
from datetime import date

from aip.product.configured.repositories.institutional_macro_scenario_repository import (
    InstitutionalMacroScenarioRepository,
)
from aip.product.economic.institutional_macro_driver import (
    EXPECTED_MACRO_DRIVER_CODES,
    InstitutionalMacroDriverSet,
    InstitutionalMonthlyMacroDrivers,
)
from aip.product.economic.institutional_macro_scenario import (
    InstitutionalMacroScenario,
)


class InstitutionalMacroDriverService:
    """
    Resolves an approved institutional macro scenario
    into homogeneous monthly driver rows.

    Responsibilities:
    - read scenario through repository;
    - require APPROVED lifecycle status;
    - require the seven institutional macro indicators;
    - require contiguous monthly trajectories;
    - reject duplicate or missing points;
    - preserve scenario/version lineage.

    This service intentionally performs no financial
    projection or balance-sheet calculation.
    """

    def __init__(
        self,
        *,
        repository: InstitutionalMacroScenarioRepository | None = None,
    ) -> None:
        self._repository = repository or InstitutionalMacroScenarioRepository()

    def build(
        self,
        *,
        scenario_id: str,
        version: int,
    ) -> InstitutionalMacroDriverSet:
        scenario = self._repository.get(
            scenario_id,
            version,
        )

        if scenario is None:
            raise ValueError("Institutional macro scenario " f"not found: {scenario_id} v{version}")

        return self.build_from_scenario(scenario)

    def build_from_scenario(
        self,
        scenario: InstitutionalMacroScenario,
    ) -> InstitutionalMacroDriverSet:
        self._validate_scenario(scenario)

        points_by_period: dict[
            date,
            dict[str, float],
        ] = defaultdict(dict)

        periods_by_indicator: dict[
            str,
            tuple[date, ...],
        ] = {}

        for indicator in scenario.indicators:
            code = indicator.indicator_code.strip().upper()

            if code not in EXPECTED_MACRO_DRIVER_CODES:
                continue

            indicator_periods: list[date] = []

            for point in indicator.points:
                period = point.target_period

                if code in points_by_period[period]:
                    raise ValueError(
                        "Duplicate macro driver point: " f"{code} {period.isoformat()}"
                    )

                points_by_period[period][code] = float(point.point_forecast)

                indicator_periods.append(period)

            periods_by_indicator[code] = tuple(indicator_periods)

        self._validate_period_alignment(
            scenario=scenario,
            periods_by_indicator=(periods_by_indicator),
        )

        ordered_periods = sorted(points_by_period)

        rows: list[InstitutionalMonthlyMacroDrivers] = []

        for period in ordered_periods:
            values = points_by_period[period]

            missing = [code for code in EXPECTED_MACRO_DRIVER_CODES if code not in values]

            if missing:
                raise ValueError(
                    "Incomplete macro driver period " f"{period.isoformat()}: " + ", ".join(missing)
                )

            rows.append(
                InstitutionalMonthlyMacroDrivers(
                    scenario_id=(scenario.scenario_id),
                    scenario_version=(scenario.version),
                    scenario_type=(scenario.scenario_type),
                    dataset_as_of_date=(scenario.dataset_as_of_date),
                    period=period,
                    fx_sell=values["FX_SELL"],
                    tpm=values["TPM"],
                    tbp=values["TBP"],
                    tri_crc_12m=values["TRI_CRC_12M"],
                    tri_usd_12m=values["TRI_USD_12M"],
                    inflation=values["INFLATION"],
                    imae=values["IMAE"],
                )
            )

        if len(rows) != scenario.horizon_months:
            raise ValueError(
                "Macro driver horizon mismatch. "
                f"Expected {scenario.horizon_months}, "
                f"received {len(rows)}."
            )

        return InstitutionalMacroDriverSet(
            scenario_id=(scenario.scenario_id),
            scenario_version=(scenario.version),
            scenario_type=(scenario.scenario_type),
            scenario_status=(scenario.status),
            dataset_as_of_date=(scenario.dataset_as_of_date),
            horizon=(scenario.horizon_months),
            rows=tuple(rows),
        )

    @staticmethod
    def _validate_scenario(
        scenario: InstitutionalMacroScenario,
    ) -> None:
        if scenario.status != "APPROVED":
            raise ValueError(
                "Macro drivers can only be built "
                "from an APPROVED scenario. "
                f"Current status: {scenario.status}"
            )

        indicator_codes = {
            indicator.indicator_code.strip().upper() for indicator in scenario.indicators
        }

        missing = [code for code in EXPECTED_MACRO_DRIVER_CODES if code not in indicator_codes]

        if missing:
            raise ValueError(
                "Approved scenario is missing " "required macro indicators: " + ", ".join(missing)
            )

        duplicates = [
            code
            for code in EXPECTED_MACRO_DRIVER_CODES
            if sum(
                1
                for indicator in scenario.indicators
                if (indicator.indicator_code.strip().upper() == code)
            )
            > 1
        ]

        if duplicates:
            raise ValueError(
                "Approved scenario contains " "duplicate indicators: " + ", ".join(duplicates)
            )

        if scenario.horizon_months < 1:
            raise ValueError("Scenario horizon must be positive.")

    @staticmethod
    def _validate_period_alignment(
        *,
        scenario: InstitutionalMacroScenario,
        periods_by_indicator: dict[
            str,
            tuple[date, ...],
        ],
    ) -> None:
        reference: (
            tuple[
                date,
                ...,
            ]
            | None
        ) = None

        reference_code: str | None = None

        for code in EXPECTED_MACRO_DRIVER_CODES:
            periods = periods_by_indicator.get(
                code,
                (),
            )

            if len(periods) != scenario.horizon_months:
                raise ValueError(
                    "Macro driver point count mismatch "
                    f"for {code}. "
                    f"Expected {scenario.horizon_months}, "
                    f"received {len(periods)}."
                )

            if len(set(periods)) != len(periods):
                raise ValueError("Duplicate target periods " f"for {code}.")

            ordered = tuple(sorted(periods))

            if reference is None:
                reference = ordered
                reference_code = code
                continue

            if ordered != reference:
                raise ValueError(
                    "Macro driver periods are not "
                    "aligned. "
                    f"{code} differs from "
                    f"{reference_code}."
                )
