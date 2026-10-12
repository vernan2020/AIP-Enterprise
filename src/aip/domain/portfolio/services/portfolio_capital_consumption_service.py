from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ExposureClass(StrEnum):
    BCCR_CRC = "BCCR_CRC"
    GOVERNMENT_CRC = "GOVERNMENT_CRC"
    RATED_0 = "RATED_0"
    RATED_1 = "RATED_1"
    RATED_2 = "RATED_2"
    RATED_3 = "RATED_3"
    RATED_4 = "RATED_4"
    RATED_5 = "RATED_5"
    RATED_6 = "RATED_6"
    UNRATED = "UNRATED"
    REPURCHASE = "REPURCHASE"


REGULATORY_WEIGHTS: dict[ExposureClass, Decimal] = {
    ExposureClass.BCCR_CRC: Decimal("0"),
    ExposureClass.GOVERNMENT_CRC: Decimal("0"),
    ExposureClass.RATED_0: Decimal("0"),
    ExposureClass.RATED_1: Decimal("0.10"),
    ExposureClass.RATED_2: Decimal("0.25"),
    ExposureClass.RATED_3: Decimal("0.50"),
    ExposureClass.RATED_4: Decimal("0.75"),
    ExposureClass.RATED_5: Decimal("0.90"),
    ExposureClass.RATED_6: Decimal("1"),
    ExposureClass.UNRATED: Decimal("1"),
    ExposureClass.REPURCHASE: Decimal("0.75"),
}


@dataclass(frozen=True, slots=True)
class CapitalExposure:
    security_key: str
    issuer: str
    currency: str
    regulatory_exposure_crc: Decimal
    exposure_class: ExposureClass
    classification_source: str


@dataclass(frozen=True, slots=True)
class CapitalExposureResult:
    security_key: str
    issuer: str
    exposure_class: ExposureClass
    risk_weight: Decimal
    regulatory_exposure_crc: Decimal
    credit_rwa_crc: Decimal
    classification_source: str


@dataclass(frozen=True, slots=True)
class PortfolioCapitalResult:
    items: tuple[CapitalExposureResult, ...]
    total_regulatory_exposure_crc: Decimal
    total_credit_rwa_crc: Decimal
    weighted_average_risk_weight: Decimal


class PortfolioCapitalConsumptionService:
    """Credit RWA attributable to investment holdings under SUGEF 3-06 v75.

    Input is the verified regulatory exposure amount in CRC, not automatically
    market value. Capital consumption is distinct from minimum capital required
    and the entire solvency denominator. Other risks are outside this service.
    """

    @staticmethod
    def evaluate(positions: tuple[CapitalExposure, ...]) -> PortfolioCapitalResult:
        if not positions:
            raise ValueError("At least one investment exposure is required")
        computed: list[CapitalExposureResult] = []
        for position in positions:
            if not position.security_key.strip() or not position.issuer.strip():
                raise ValueError("Security and issuer are required")
            if not position.classification_source.strip():
                raise ValueError("Classification source or approved decision is required")
            if position.regulatory_exposure_crc < 0 or not position.regulatory_exposure_crc.is_finite():
                raise ValueError("Regulatory exposure must be finite and non-negative")
            if position.currency.upper() != "CRC" and position.exposure_class in {
                ExposureClass.BCCR_CRC,
                ExposureClass.GOVERNMENT_CRC,
            }:
                raise ValueError("CRC sovereign zero-weight classification requires CRC currency")
            try:
                weight = REGULATORY_WEIGHTS[position.exposure_class]
            except KeyError as exc:
                raise ValueError("Unrecognized regulatory exposure classification") from exc
            computed.append(
                CapitalExposureResult(
                    security_key=position.security_key,
                    issuer=position.issuer,
                    exposure_class=position.exposure_class,
                    risk_weight=weight,
                    regulatory_exposure_crc=position.regulatory_exposure_crc,
                    credit_rwa_crc=position.regulatory_exposure_crc * weight,
                    classification_source=position.classification_source,
                )
            )
        total = sum((x.regulatory_exposure_crc for x in computed), Decimal("0"))
        rwa = sum((x.credit_rwa_crc for x in computed), Decimal("0"))
        return PortfolioCapitalResult(
            items=tuple(computed),
            total_regulatory_exposure_crc=total,
            total_credit_rwa_crc=rwa,
            weighted_average_risk_weight=rwa / total if total else Decimal("0"),
        )
