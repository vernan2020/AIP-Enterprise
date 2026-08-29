from __future__ import annotations

from dataclasses import dataclass
from datetime import date

EXPECTED_MACRO_DRIVER_CODES: tuple[str, ...] = (
    "FX_SELL",
    "TPM",
    "TBP",
    "TRI_CRC_12M",
    "TRI_USD_12M",
    "INFLATION",
    "IMAE",
)


@dataclass(
    frozen=True,
    slots=True,
)
class InstitutionalMacroDriverPoint:
    """
    One projected institutional macro driver.

    The point keeps the source indicator and target
    period explicitly for auditability.
    """

    indicator_code: str
    target_period: date
    value: float
    lower_bound: float | None
    upper_bound: float | None
    confidence_level: float | None


@dataclass(
    frozen=True,
    slots=True,
)
class InstitutionalMonthlyMacroDrivers:
    """
    Homogeneous monthly macroeconomic driver vector.

    No financial-impact logic belongs in this object.
    """

    scenario_id: str
    scenario_version: int
    scenario_type: str
    dataset_as_of_date: date
    period: date

    fx_sell: float
    tpm: float
    tbp: float
    tri_crc_12m: float
    tri_usd_12m: float
    inflation: float
    imae: float

    @property
    def values_by_code(
        self,
    ) -> dict[str, float]:
        return {
            "FX_SELL": self.fx_sell,
            "TPM": self.tpm,
            "TBP": self.tbp,
            "TRI_CRC_12M": self.tri_crc_12m,
            "TRI_USD_12M": self.tri_usd_12m,
            "INFLATION": self.inflation,
            "IMAE": self.imae,
        }


@dataclass(
    frozen=True,
    slots=True,
)
class InstitutionalMacroDriverSet:
    """
    Version-bound macro trajectory consumed by
    downstream financial projection engines.
    """

    scenario_id: str
    scenario_version: int
    scenario_type: str
    scenario_status: str
    dataset_as_of_date: date
    horizon: int
    rows: tuple[
        InstitutionalMonthlyMacroDrivers,
        ...,
    ]

    @property
    def row_count(
        self,
    ) -> int:
        return len(
            self.rows
        )

    @property
    def first_period(
        self,
    ) -> date | None:
        if not self.rows:
            return None

        return self.rows[0].period

    @property
    def last_period(
        self,
    ) -> date | None:
        if not self.rows:
            return None

        return self.rows[-1].period

    def row_for_period(
        self,
        period: date,
    ) -> InstitutionalMonthlyMacroDrivers | None:
        for row in self.rows:
            if row.period == period:
                return row

        return None
