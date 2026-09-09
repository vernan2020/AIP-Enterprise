from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowDirection,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapBucketTotal,
    SugefGapExposure,
    SugefGapExposureType,
    SugefGapScheduleRecord,
)
from aip.shared.money import Money


class SugefStandardGapService:
    """Build and aggregate exposures for the SUGEF 19-band GAP template.

    This service intentionally remains separate from the EVE cash-flow engine.
    For fixed-rate positions, contractual payments are assigned to their payment
    dates. For floating or semivariable positions represented by ``RateType.FLOATING``,
    contractual payments through the next repricing date remain in their payment
    bands and only the outstanding principal is assigned to the repricing date.
    Payments and interest after that repricing date are not carried forward at the
    current rate merely to populate the regulatory GAP report.
    """

    @classmethod
    def build_exposures(
        cls,
        *,
        position: BankingBookPosition,
        schedule: tuple[SugefGapScheduleRecord, ...],
        valuation_date: date,
    ) -> tuple[SugefGapExposure, ...]:
        records = cls._validated_schedule(
            position=position,
            schedule=schedule,
            valuation_date=valuation_date,
        )

        if position.rate_type is RateType.FIXED:
            return cls._fixed_exposures(position=position, records=records)

        repricing_date = position.next_repricing_date
        if repricing_date is None:
            raise ValueError("floating-rate position requires next_repricing_date")
        if repricing_date < valuation_date:
            raise ValueError("next_repricing_date cannot be before valuation_date")
        if position.maturity_date is not None and repricing_date >= position.maturity_date:
            return cls._fixed_exposures(position=position, records=records)

        included = tuple(record for record in records if record.payment_date <= repricing_date)
        exposures = list(cls._fixed_exposures(position=position, records=included))
        residual = cls._residual_principal_at_repricing(
            position=position,
            included_records=included,
        )
        if residual.amount > 0:
            exposures.append(
                SugefGapExposure(
                    position_id=position.position_id,
                    side=position.side,
                    direction=cls._principal_direction(position.side),
                    amount=residual,
                    risk_date=repricing_date,
                    exposure_type=SugefGapExposureType.REPRICING_PRINCIPAL,
                    source_reference=(
                        f"{position.source_reference}|OUTSTANDING_PRINCIPAL_AT_REPRICING"
                    ),
                )
            )

        exposures.sort(key=lambda item: (item.risk_date, item.exposure_type.value))
        return tuple(exposures)

    @classmethod
    def aggregate_by_bucket(
        cls,
        *,
        exposures: tuple[SugefGapExposure, ...],
        valuation_date: date,
    ) -> tuple[SugefGapBucketTotal, ...]:
        if not exposures:
            return ()

        currency = exposures[0].amount.currency
        totals: dict[object, Decimal] = {}
        metadata: dict[object, tuple[int, str]] = {}

        for exposure in exposures:
            if exposure.amount.currency is not currency:
                raise ValueError("gap aggregation requires a single currency")
            assignment = IRRBBTimeBucketService.assign(
                valuation_date=valuation_date,
                risk_date=exposure.risk_date,
            )
            totals[assignment.bucket] = totals.get(assignment.bucket, Decimal("0")) + (
                exposure.amount.amount
            )
            metadata[assignment.bucket] = (assignment.ordinal, assignment.label)

        ordered = sorted(totals, key=lambda bucket: metadata[bucket][0])
        return tuple(
            SugefGapBucketTotal(
                bucket=bucket,
                ordinal=metadata[bucket][0],
                label=metadata[bucket][1],
                amount=Money(totals[bucket], currency),
            )
            for bucket in ordered
        )

    @staticmethod
    def _validated_schedule(
        *,
        position: BankingBookPosition,
        schedule: tuple[SugefGapScheduleRecord, ...],
        valuation_date: date,
    ) -> tuple[SugefGapScheduleRecord, ...]:
        records = tuple(sorted(schedule, key=lambda item: (item.payment_date, item.flow_type)))
        for record in records:
            if record.amount.currency is not position.currency:
                raise ValueError("schedule currency must match position currency")
            if record.payment_date < valuation_date:
                raise ValueError("schedule contains a payment before valuation_date")
        return records

    @staticmethod
    def _fixed_exposures(
        *,
        position: BankingBookPosition,
        records: tuple[SugefGapScheduleRecord, ...],
    ) -> tuple[SugefGapExposure, ...]:
        return tuple(
            SugefGapExposure(
                position_id=position.position_id,
                side=position.side,
                direction=record.direction,
                amount=record.amount,
                risk_date=record.payment_date,
                exposure_type=SugefGapExposureType.CONTRACTUAL_PAYMENT,
                source_reference=record.source_reference,
            )
            for record in records
        )

    @classmethod
    def _residual_principal_at_repricing(
        cls,
        *,
        position: BankingBookPosition,
        included_records: tuple[SugefGapScheduleRecord, ...],
    ) -> Money:
        if included_records:
            latest_direct_balance = next(
                (
                    record.outstanding_principal_after
                    for record in reversed(included_records)
                    if record.outstanding_principal_after is not None
                ),
                None,
            )
            if latest_direct_balance is not None:
                cls._validate_residual(position=position, residual=latest_direct_balance)
                return latest_direct_balance

        if position.payment_structure is PaymentStructure.BULLET:
            principal_paid = sum(
                (
                    record.principal_component.amount
                    for record in included_records
                    if record.principal_component is not None
                ),
                Decimal("0"),
            )
            residual = Money(position.principal.amount - principal_paid, position.currency)
            cls._validate_residual(position=position, residual=residual)
            return residual

        if not included_records:
            return position.principal

        missing_components = tuple(
            record
            for record in included_records
            if record.principal_component is None
            and record.amount.amount > 0
            and record.flow_type.upper() not in {"INTEREST", "COUPON", "FEE"}
        )
        if missing_components:
            raise ValueError(
                "amortizing floating-rate position requires outstanding_principal_after "
                "or principal_component for payments through repricing"
            )

        principal_paid = sum(
            (
                record.principal_component.amount
                for record in included_records
                if record.principal_component is not None
            ),
            Decimal("0"),
        )
        residual = Money(position.principal.amount - principal_paid, position.currency)
        cls._validate_residual(position=position, residual=residual)
        return residual

    @staticmethod
    def _validate_residual(*, position: BankingBookPosition, residual: Money) -> None:
        if residual.currency is not position.currency:
            raise ValueError("residual principal currency must match position currency")
        if residual.amount < 0:
            raise ValueError("residual principal cannot be negative")
        if residual.amount > position.principal.amount:
            raise ValueError("residual principal cannot exceed current principal")

    @staticmethod
    def _principal_direction(side: BankingBookSide) -> CashFlowDirection:
        if side is BankingBookSide.ASSET:
            return CashFlowDirection.RECEIVABLE
        if side is BankingBookSide.LIABILITY:
            return CashFlowDirection.PAYABLE
        raise ValueError("off-balance repricing principal requires an explicit strategy")
