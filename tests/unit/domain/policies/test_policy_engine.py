from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.base.policy_result import PolicyResult
from aip.domain.policies.composition.and_policy import AndPolicy
from aip.domain.policies.composition.not_policy import NotPolicy
from aip.domain.policies.composition.or_policy import OrPolicy
from aip.domain.policies.engine.policy_engine import PolicyEngine
from aip.domain.policies.evaluation.evaluation_report import EvaluationReport
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.exceptions import PolicyDependencyError, PolicyValidationError
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.registry.policy_registry import PolicyRegistry
from aip.domain.policies.severity.policy_severity import PolicySeverity


class RecordingPolicy(Policy):
    def __init__(self, policy_id: str, *, status: PolicySeverity, enabled: bool = True) -> None:
        super().__init__(
            policy_id=policy_id,
            name=policy_id,
            description="recording policy",
            version="1.0",
            enabled=enabled,
            severity=PolicySeverity.MEDIUM,
            category="test",
            reference=None,
            tags=("test",),
        )
        self.status = status
        self.call_count = 0

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        self.call_count += 1
        return EvaluationResult(
            policy_id=self.policy_id,
            status=self.status,
            message="recorded",
            severity=self.severity,
            references=(),
            timestamp=datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )


class PassingPolicy(Policy):
    def __init__(self, policy_id: str, *, enabled: bool = True) -> None:
        super().__init__(
            policy_id=policy_id,
            name=policy_id,
            description="passing policy",
            version="1.0",
            enabled=enabled,
            severity=PolicySeverity.LOW,
            category="test",
            reference=PolicyReference(source="tests", identifier=policy_id),
            tags=("pass",),
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status="PASSED",
            message="passed",
            severity=self.severity,
            references=(self.reference,) if self.reference else (),
            timestamp=datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )


class WarningPolicy(Policy):
    def __init__(self, policy_id: str) -> None:
        super().__init__(
            policy_id=policy_id,
            name=policy_id,
            description="warning policy",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="test",
            reference=None,
            tags=("warn",),
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status="WARNING",
            message="warning",
            severity=self.severity,
            references=(),
            timestamp=datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )


class FailingPolicy(Policy):
    def __init__(self, policy_id: str, *, enabled: bool = True) -> None:
        super().__init__(
            policy_id=policy_id,
            name=policy_id,
            description="failing policy",
            version="1.0",
            enabled=enabled,
            severity=PolicySeverity.HIGH,
            category="test",
            reference=None,
            tags=("fail",),
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status="FAILED",
            message="failed",
            severity=self.severity,
            references=(),
            timestamp=datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )


class DependentPolicy(Policy):
    def __init__(self, policy_id: str, dependencies: tuple[str, ...]) -> None:
        super().__init__(
            policy_id=policy_id,
            name=policy_id,
            description="dependent policy",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="test",
            reference=None,
            dependencies=dependencies,
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status="PASSED",
            message="dep passed",
            severity=self.severity,
            references=(),
            timestamp=datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )


class DependencyAwarePolicy(Policy):
    def __init__(self, policy_id: str, dependencies: tuple[str, ...]) -> None:
        super().__init__(
            policy_id=policy_id,
            name=policy_id,
            description="dependency-aware",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="test",
            reference=None,
            dependencies=dependencies,
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        return EvaluationResult(
            policy_id=self.policy_id,
            status="PASSED",
            message="dep passed",
            severity=self.severity,
            references=(),
            timestamp=datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )


def test_composite_evaluation_short_circuits_in_deterministic_order() -> None:
    engine = PolicyEngine()
    context = PolicyContext(context_id="ctx-comp")
    failing = FailingPolicy("failing")
    recording = RecordingPolicy("recording", status="PASSED")

    and_policy = AndPolicy((failing, recording))
    result = engine.evaluate(and_policy, context)
    assert result.status == "FAILED"
    assert recording.call_count == 0

    passing = PassingPolicy("passing")
    or_policy = OrPolicy((failing, passing))
    result = engine.evaluate(or_policy, context)
    assert result.status == "PASSED"

    not_policy = NotPolicy(failing)
    result = engine.evaluate(not_policy, context)
    assert result.status == "PASSED"

    composite = AndPolicy((passing, NotPolicy(failing)))
    report = engine.evaluate_many((composite,), context)
    assert isinstance(report, EvaluationReport)
    assert report.overall_status == "PASSED"


def test_dependencies_are_resolved_before_evaluation() -> None:
    engine = PolicyEngine()
    context = PolicyContext(context_id="ctx-dep")
    dependency = PassingPolicy("dependency")
    dependent = DependencyAwarePolicy("dependent", dependencies=("dependency",))

    engine.register(dependency)
    engine.register(dependent)

    result = engine.evaluate(dependent, context)
    assert result.status == "PASSED"

    missing = DependentPolicy("missing", dependencies=("does-not-exist",))
    result = engine.evaluate(missing, context)
    assert result.status == "NOT_APPLICABLE"
    assert "dependency" in result.message.lower()


def test_disabled_policies_return_not_applicable() -> None:
    engine = PolicyEngine()
    context = PolicyContext(context_id="ctx-disabled")
    policy = PassingPolicy("disabled", enabled=False)
    result = engine.evaluate(policy, context)
    assert result.status == "NOT_APPLICABLE"
    assert result.message == "Policy is disabled"


def test_severity_ordering_is_deterministic() -> None:
    severities = [
        PolicySeverity.CRITICAL,
        PolicySeverity.HIGH,
        PolicySeverity.MEDIUM,
        PolicySeverity.LOW,
        PolicySeverity.INFO,
    ]
    ordered = sorted(severities, key=lambda severity: severity.rank())
    assert ordered[0] is PolicySeverity.INFO
    assert ordered[-1] is PolicySeverity.CRITICAL


def test_registry_supports_lookup_by_id_category_and_tags() -> None:
    registry = PolicyRegistry()
    policy = PassingPolicy("registry-policy")
    registry.register(policy)

    assert registry.get("registry-policy") is policy
    assert registry.get_by_category("test") == [policy]
    assert registry.get_by_tags(("pass",)) == [policy]


def test_invalid_policies_and_duplicate_registry_entries_raise_errors() -> None:
    class InvalidPolicy(Policy):
        def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
            return EvaluationResult(
                policy_id="invalid",
                status="PASSED",
                message="",
                severity=PolicySeverity.LOW,
                references=(),
                timestamp=datetime.now(timezone.utc),
                evaluation_duration=None,
                context_id=context.context_id,
            )

    with pytest.raises(PolicyValidationError):
        InvalidPolicy("", "name", "description", "1.0", True, PolicySeverity.LOW, "cat", None)

    registry = PolicyRegistry()
    first = PassingPolicy("dup")
    second = PassingPolicy("dup")
    registry.register(first)
    with pytest.raises(PolicyValidationError):
        registry.register(second)


def test_policy_result_and_reference_models_are_frozen_and_traceable() -> None:
    reference = PolicyReference(source="reg", identifier="ref-1", url="https://example.com")
    result = PolicyResult(
        policy_id="policy",
        status="WARNING",
        message="needs review",
        severity=PolicySeverity.MEDIUM,
        references=(reference,),
        timestamp=datetime.now(timezone.utc),
        evaluation_duration=None,
        context_id="ctx-result",
    )
    assert result.context_id == "ctx-result"
    assert result.references[0].identifier == "ref-1"
    assert result.to_dict()["status"] == "WARNING"


def test_policy_engine_handles_priority_and_circular_dependency_paths() -> None:
    engine = PolicyEngine()
    context = PolicyContext(context_id="ctx-priority")

    policy = PassingPolicy("priority-policy")
    policy.priority = 3
    engine.register(policy)

    report = engine.evaluate_many((policy,), context)
    assert report.overall_status == "PASSED"

    warning_policy = WarningPolicy("warning-policy")
    report = engine.evaluate_many((warning_policy,), context)
    assert report.overall_status == "WARNING"

    disabled_policy = PassingPolicy("disabled-policy", enabled=False)
    report = engine.evaluate_many((disabled_policy,), context)
    assert report.overall_status == "NOT_APPLICABLE"

    circular = DependencyAwarePolicy("circular", dependencies=("circular",))
    engine.register(circular)
    with pytest.raises(PolicyDependencyError):
        engine._evaluate_policy(circular, context, seen=("circular",))


def test_validation_errors_cover_constructor_and_composite_requirements() -> None:
    class ConcretePolicy(Policy):
        def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
            return EvaluationResult(
                policy_id=self.policy_id,
                status="PASSED",
                message="ok",
                severity=self.severity,
                references=(),
                timestamp=datetime.now(timezone.utc),
                evaluation_duration=None,
                context_id=context.context_id,
            )

    with pytest.raises(PolicyValidationError):
        ConcretePolicy("", "name", "description", "1.0", True, PolicySeverity.LOW, "")
    with pytest.raises(PolicyValidationError):
        ConcretePolicy("id", "name", "description", "1.0", True, "LOW", "category")

    with pytest.raises(PolicyValidationError):
        ConcretePolicy("id", "", "description", "1.0", True, PolicySeverity.LOW, "category")
