from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class MacroProjectionRow:
    """One monthly row from the governed institutional macro scenario."""

    period: date
    fx_sell: float
    tpm: float
    tbp: float
    tri_crc_12m: float
    tri_usd_12m: float
    inflation: float
    imae: float

    def value_for(self, code: str) -> float:
        mapping = {
            "FX_SELL": self.fx_sell,
            "TPM": self.tpm,
            "TBP": self.tbp,
            "TRI_CRC_12M": self.tri_crc_12m,
            "TRI_USD_12M": self.tri_usd_12m,
            "INFLATION": self.inflation,
            "IMAE": self.imae,
        }
        return mapping[code]


@dataclass(frozen=True, slots=True)
class MacroProjectionViewModel:
    """Immutable presentation contract for the approved macro scenario."""

    status: str = "UNAVAILABLE"
    scenario_id: str = "-"
    version: int = 0
    scenario_type: str = "-"
    scenario_status: str = "-"
    dataset_as_of_date: date | None = None
    horizon: int = 0
    rows: tuple[MacroProjectionRow, ...] = field(default_factory=tuple)
    diagnostic: str | None = None

    @property
    def first_period(self) -> date | None:
        return self.rows[0].period if self.rows else None

    @property
    def last_period(self) -> date | None:
        return self.rows[-1].period if self.rows else None
