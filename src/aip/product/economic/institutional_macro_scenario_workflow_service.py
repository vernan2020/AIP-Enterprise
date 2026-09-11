from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from aip.product.configured.repositories.institutional_macro_scenario_repository import (
    InstitutionalMacroScenarioRepository,
)
from aip.product.economic.institutional_macro_scenario_workflow import (
    ScenarioReviewResolution,
    ScenarioWorkflowEvent,
)


class InstitutionalMacroScenarioWorkflowService:
    """
    Governs institutional scenario lifecycle.

    Forecast trajectories remain immutable.

    Workflow transitions and human review resolutions
    are explicitly persisted and audited.
    """

    def __init__(
        self,
        *,
        repository: InstitutionalMacroScenarioRepository | None = None,
    ) -> None:
        self._repository = repository or InstitutionalMacroScenarioRepository()

    @property
    def repository(
        self,
    ) -> InstitutionalMacroScenarioRepository:
        return self._repository

    @staticmethod
    def _normalize_actor(
        actor: str,
    ) -> str:
        normalized = actor.strip()

        if not normalized:
            raise ValueError("actor cannot be empty")

        return normalized

    @staticmethod
    def _require_text(
        value: str,
        *,
        field_name: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be empty")

        return normalized

    def resolve_review(
        self,
        *,
        scenario_id: str,
        version: int,
        indicator_code: str,
        resolution: str,
        actor: str,
        comment: str,
        reason: str,
    ) -> ScenarioReviewResolution:
        scenario = self._repository.get(
            scenario_id,
            version,
        )

        if scenario is None:
            raise ValueError("Scenario version does not exist: " f"{scenario_id} v{version}")

        if scenario.status != "DRAFT":
            raise ValueError("Review resolution is only permitted " "while scenario is DRAFT")

        code = indicator_code.strip().upper()

        indicator = scenario.indicator(code)

        if indicator is None:
            raise ValueError("Indicator does not exist in scenario: " f"{code}")

        if indicator.institutional_status != "REVIEW_REQUIRED":
            raise ValueError("Indicator does not require review: " f"{code}")

        normalized_resolution = resolution.strip().upper()

        if normalized_resolution not in {
            "ACCEPTED_FOR_SCENARIO",
            "OVERRIDDEN",
            "REJECTED",
        }:
            raise ValueError("Unsupported review resolution: " f"{resolution}")

        normalized_actor = self._normalize_actor(actor)

        normalized_comment = self._require_text(
            comment,
            field_name="comment",
        )

        normalized_reason = self._require_text(
            reason,
            field_name="reason",
        )

        now = datetime.now(timezone.utc)

        review = ScenarioReviewResolution(
            scenario_id=(scenario.scenario_id),
            version=scenario.version,
            indicator_code=code,
            resolution=(normalized_resolution),
            actor=normalized_actor,
            resolved_at=now,
            comment=normalized_comment,
            reason=normalized_reason,
        )

        event = ScenarioWorkflowEvent(
            event_id=uuid4().hex,
            scenario_id=(scenario.scenario_id),
            version=scenario.version,
            event_type="REVIEW_RESOLVED",
            from_status=scenario.status,
            to_status=scenario.status,
            actor=normalized_actor,
            event_at=now,
            comment=normalized_comment,
            reason=(f"{code}: " f"{normalized_resolution}; " f"{normalized_reason}"),
        )

        self._repository.save_review_resolution(
            review,
            event,
        )

        return review

    def approve(
        self,
        *,
        scenario_id: str,
        version: int,
        actor: str,
        comment: str,
        reason: str,
    ):
        scenario = self._repository.get(
            scenario_id,
            version,
        )

        if scenario is None:
            raise ValueError("Scenario version does not exist: " f"{scenario_id} v{version}")

        if scenario.status != "DRAFT":
            raise ValueError("Only DRAFT scenarios can be approved")

        normalized_actor = self._normalize_actor(actor)

        normalized_comment = self._require_text(
            comment,
            field_name="comment",
        )

        normalized_reason = self._require_text(
            reason,
            field_name="reason",
        )

        resolutions = {
            item.indicator_code: item
            for item in (
                self._repository.review_resolutions(
                    scenario.scenario_id,
                    scenario.version,
                )
            )
        }

        blockers = []

        for indicator in scenario.indicators:
            if indicator.institutional_status != "REVIEW_REQUIRED":
                continue

            resolution = resolutions.get(indicator.indicator_code)

            if resolution is None:
                blockers.append(f"{indicator.indicator_code}: " "review unresolved")

                continue

            if not resolution.permits_approval:
                blockers.append(f"{indicator.indicator_code}: " f"{resolution.resolution}")

        if blockers:
            raise ValueError("Scenario cannot be approved. " + "; ".join(blockers))

        now = datetime.now(timezone.utc)

        approved_event = ScenarioWorkflowEvent(
            event_id=uuid4().hex,
            scenario_id=scenario.scenario_id,
            version=scenario.version,
            event_type="APPROVED",
            from_status="DRAFT",
            to_status="APPROVED",
            actor=normalized_actor,
            event_at=now,
            comment=normalized_comment,
            reason=normalized_reason,
        )

        superseded_events = []

        approved_versions = self._repository.approved_versions_for_scenario(
            scenario_id=(scenario.scenario_id),
            scenario_type=(scenario.scenario_type),
        )

        for (
            previous_scenario_id,
            previous_version,
        ) in approved_versions:
            if (
                previous_scenario_id == scenario.scenario_id
                and previous_version == scenario.version
            ):
                continue

            superseded_events.append(
                ScenarioWorkflowEvent(
                    event_id=uuid4().hex,
                    scenario_id=(previous_scenario_id),
                    version=(previous_version),
                    event_type="SUPERSEDED",
                    from_status="APPROVED",
                    to_status="SUPERSEDED",
                    actor=normalized_actor,
                    event_at=now,
                    comment=("Superseded by " f"{scenario.scenario_id} " f"v{scenario.version}"),
                    reason=normalized_reason,
                )
            )

        self._repository.approve_version(
            scenario_id=(scenario.scenario_id),
            version=scenario.version,
            actor=normalized_actor,
            approved_at=now,
            comment=normalized_comment,
            reason=normalized_reason,
            approved_event=approved_event,
            superseded_events=tuple(superseded_events),
        )

        loaded = self._repository.get(
            scenario.scenario_id,
            scenario.version,
        )

        if loaded is None:
            raise RuntimeError("Approved scenario could not be " "read back")

        return loaded
