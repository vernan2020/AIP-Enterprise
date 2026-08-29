from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ScenarioWorkflowEventType = Literal[
    "CREATED",
    "REVIEW_RESOLVED",
    "APPROVED",
    "SUPERSEDED",
]

ReviewResolution = Literal[
    "ACCEPTED_FOR_SCENARIO",
    "OVERRIDDEN",
    "REJECTED",
]


@dataclass(frozen=True, slots=True)
class ScenarioWorkflowEvent:
    event_id: str

    scenario_id: str
    version: int

    event_type: ScenarioWorkflowEventType

    from_status: str | None
    to_status: str | None

    actor: str
    event_at: datetime

    comment: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ScenarioReviewResolution:
    scenario_id: str
    version: int

    indicator_code: str

    resolution: ReviewResolution

    actor: str
    resolved_at: datetime

    comment: str
    reason: str

    @property
    def permits_approval(self) -> bool:
        """
        Only explicit acceptance of the model trajectory
        permits approval in Phase 4.1.

        OVERRIDDEN remains blocked until a replacement
        trajectory is actually persisted and governed.
        """
        return (
            self.resolution
            == "ACCEPTED_FOR_SCENARIO"
        )

    @property
    def requires_override_trajectory(self) -> bool:
        return (
            self.resolution
            == "OVERRIDDEN"
        )
