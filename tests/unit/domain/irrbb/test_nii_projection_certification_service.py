from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    RateType,
)
from aip.domain.irrbb.nii import (
    NIIAccrualType,
    NIIBalanceSheetAssumption,
    NIIInterestAccrual,
    NIIProjectionBasis,
    NIIShockTiming,
)
from aip.domain.irrbb.nii_certification import NIIProjectionCertificationStatus
from aip.domain.irrbb.nii_projection import (
    NIIPositionProjection,
    NIIPositionProjectionStatus,
)
from aip.domain.irrbb.nii_readiness import (
    NIIProjectionCapabilityEvidence,
    NIIProjectionEvidenceAlternative,
    NIIProjectionEvidenceKey,
    NIIProjectionRequirement,
    NIIProjectionRequirementProfile,
    NIIProjectionScopeStatus,
)
from aip.domain.irrbb.services.nii_projection_certification_service import (
    NIIProjectionCertificationService,
)
from aip.shared.money import Currency, Money


def _basis() -> NIIProjectionBasis:
    return NIIProjectionBasis(
        methodology=IRRBBMethodologyProfile(
            code="INTERNAL-NII",
            version="2026.09.10",
            status=IRRBBMethodologyStatus.INTERNAL,
            source_reference="policy:nii",
        ),
        valuation_date=date(2026, 9, 10),
        horizon_end_date=date(2027, 9, 10),
        balance_sheet_assumption=NIIBalanceSheetAssumption.CONSTANT,
        shock_timing=NIIShockTiming.INSTANTANEOUS,
        source_reference="projection:approved-input",
    )


def _position(position_id: str, *, contractual_rate: Decimal | None = Decimal("0.05")) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type="TEST",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 6, 30),
        source_reference=f"source:{position_id}",
        contractual_rate=contractual_rate,
    )


def _requirement(key: NIIProjectionEvidenceKey) -> NIIProjectionRequirement:
    return NIIProjectionRequirement(
        requirement_id=f"require-{key.value.lower()}",
        alternatives=(NIIProjectionEvidenceAlternative(keys=frozenset({key})),),
        message=f"{key.value} is required.",
    )


def _included_profile(
    strategy_reference: str,
    *requirements: NIIProjectionRequirement,
) -> NIIProjectionRequirementProfile:
    return NIIProjectionRequirementProfile(
        strategy_reference=strategy_reference,
        source_reference=f"policy:{strategy_reference}",
        scope_status=NIIProjectionScopeStatus.INCLUDED,
        requirements=tuple(requirements),
    )


def _excluded_profile(strategy_reference: str) -> NIIProjectionRequirementProfile:
    return NIIProjectionRequirementProfile(
        strategy_reference=strategy_reference,
        source_reference=f"policy:{strategy_reference}",
        scope_status=NIIProjectionScopeStatus.EXCLUDED,
        exclusion_reason="Outside approved NII perimeter.",
    )


class _ProfileProvider:
    def __init__(self, profiles: dict[str, NIIProjectionRequirementProfile]) -> None:
        self._profiles = profiles
        self.calls: list[str] = []

    def profile_for(self, *, position: BankingBookPosition) -> NIIProjectionRequirementProfile:
        self.calls.append(position.position_id)
        return self._profiles[position.position_id]


class _CapabilityProvider:
    def __init__(
        self,
        evidence: dict[str, tuple[NIIProjectionCapabilityEvidence, ...]] | None = None,
    ) -> None:
        self._evidence = evidence or {}
        self.calls: list[str] = []

    def evidence_for(
        self,
        *,
        position: BankingBookPosition,
        profile: NIIProjectionRequirementProfile,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> tuple[NIIProjectionCapabilityEvidence, ...]:
        assert profile.strategy_reference
        assert basis == _basis()
        assert scenario is IRRBBScenario.PARALLEL_UP
        self.calls.append(position.position_id)
        return self._evidence.get(position.position_id, ())


class _Strategy:
    def __init__(self, strategy_reference: str) -> None:
        self._strategy_reference = strategy_reference
        self.calls: list[str] = []

    def project(
        self,
        *,
        position: BankingBookPosition,
        basis: NIIProjectionBasis,
        scenario: IRRBBScenario,
    ) -> NIIPositionProjection:
        self.calls.append(position.position_id)
        accrual = NIIInterestAccrual(
            accrual_id=f"{position.position_id}:{scenario.value}:1",
            position_id=position.position_id,
            scenario=scenario,
            accrual_type=NIIAccrualType.INTEREST_INCOME,
            amount=Money(Decimal("10"), Currency.CRC),
            accrual_start_date=basis.valuation_date,
            accrual_end_date=date(2026, 10, 10),
            source_reference=f"projection:{position.position_id}",
        )
        return NIIPositionProjection(
            position_id=position.position_id,
            scenario=scenario,
            basis=basis,
            strategy_reference=self._strategy_reference,
            status=NIIPositionProjectionStatus.PROJECTED,
            accruals=(accrual,),
        )


class _Resolver:
    def __init__(self, strategies: dict[str, _Strategy]) -> None:
        self._strategies = strategies
        self.calls: list[str] = []

    def resolve(self, *, position: BankingBookPosition) -> _Strategy:
        self.calls.append(position.position_id)
        return self._strategies[position.position_id]


def test_certifies_every_position_before_projecting_ready_scope() -> None:
    positions = (_position("p1"), _position("p2"), _position("excluded"))
    profiles = {
        "p1": _included_profile("strategy:p1", _requirement(NIIProjectionEvidenceKey.CONTRACTUAL_RATE)),
        "p2": _included_profile(
            "strategy:p2",
            _requirement(NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE),
        ),
        "excluded": _excluded_profile("strategy:excluded"),
    }
    profile_provider = _ProfileProvider(profiles)
    capability_provider = _CapabilityProvider(
        {
            "p2": (
                NIIProjectionCapabilityEvidence(
                    key=NIIProjectionEvidenceKey.FORWARD_REFERENCE_RATE_CURVE,
                    source_reference="curve:tri-crc:approved:v1",
                ),
            )
        }
    )
    resolver = _Resolver(
        {
            "p1": _Strategy("strategy:p1"),
            "p2": _Strategy("strategy:p2"),
        }
    )

    result = NIIProjectionCertificationService.project_certified(
        positions=positions,
        basis=_basis(),
        scenario=IRRBBScenario.PARALLEL_UP,
        profile_provider=profile_provider,
        capability_provider=capability_provider,
        strategy_resolver=resolver,
    )

    assert result.status is NIIProjectionCertificationStatus.PROJECTED
    assert [item.position_id for item in result.assessments] == ["p1", "p2", "excluded"]
    assert result.projection_batch is not None
    assert [item.position_id for item in result.projection_batch.projections] == ["p1", "p2"]
    assert profile_provider.calls == ["p1", "p2", "excluded"]
    assert capability_provider.calls == ["p1", "p2"]
    assert resolver.calls == ["p1", "p2"]


def test_one_blocked_position_prevents_every_strategy_from_running() -> None:
    positions = (_position("ready"), _position("blocked", contractual_rate=None))
    profile_provider = _ProfileProvider(
        {
            position.position_id: _included_profile(
                f"strategy:{position.position_id}",
                _requirement(NIIProjectionEvidenceKey.CONTRACTUAL_RATE),
            )
            for position in positions
        }
    )
    capability_provider = _CapabilityProvider()
    resolver = _Resolver(
        {
            "ready": _Strategy("strategy:ready"),
            "blocked": _Strategy("strategy:blocked"),
        }
    )

    result = NIIProjectionCertificationService.project_certified(
        positions=positions,
        basis=_basis(),
        scenario=IRRBBScenario.PARALLEL_UP,
        profile_provider=profile_provider,
        capability_provider=capability_provider,
        strategy_resolver=resolver,
    )

    assert result.status is NIIProjectionCertificationStatus.BLOCKED
    assert result.projection_batch is None
    assert resolver.calls == []


def test_excluded_only_portfolio_does_not_request_capabilities_or_strategies() -> None:
    positions = (_position("p1"), _position("p2"))
    profile_provider = _ProfileProvider(
        {position.position_id: _excluded_profile(f"strategy:{position.position_id}") for position in positions}
    )
    capability_provider = _CapabilityProvider()
    resolver = _Resolver({})

    result = NIIProjectionCertificationService.project_certified(
        positions=positions,
        basis=_basis(),
        scenario=IRRBBScenario.PARALLEL_UP,
        profile_provider=profile_provider,
        capability_provider=capability_provider,
        strategy_resolver=resolver,
    )

    assert result.status is NIIProjectionCertificationStatus.NO_INCLUDED_POSITIONS
    assert result.projection_batch is None
    assert capability_provider.calls == []
    assert resolver.calls == []


def test_projection_strategy_reference_must_match_approved_profile() -> None:
    position = _position("p1")
    profile_provider = _ProfileProvider(
        {"p1": _included_profile("strategy:approved")}
    )
    resolver = _Resolver({"p1": _Strategy("strategy:substituted")})

    with pytest.raises(ValueError, match="strategy_reference does not match profile"):
        NIIProjectionCertificationService.project_certified(
            positions=(position,),
            basis=_basis(),
            scenario=IRRBBScenario.PARALLEL_UP,
            profile_provider=profile_provider,
            capability_provider=_CapabilityProvider(),
            strategy_resolver=resolver,
        )


def test_duplicate_positions_fail_before_any_provider_is_called() -> None:
    profile_provider = _ProfileProvider({})
    capability_provider = _CapabilityProvider()
    resolver = _Resolver({})

    with pytest.raises(ValueError, match="duplicate NII projection certification position_id"):
        NIIProjectionCertificationService.project_certified(
            positions=(_position("p1"), _position("p1")),
            basis=_basis(),
            scenario=IRRBBScenario.PARALLEL_UP,
            profile_provider=profile_provider,
            capability_provider=capability_provider,
            strategy_resolver=resolver,
        )

    assert profile_provider.calls == []
    assert capability_provider.calls == []
    assert resolver.calls == []
