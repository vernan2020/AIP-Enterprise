from __future__ import annotations

from dataclasses import dataclass, field

from aip.integration.audit.synchronization_log import SynchronizationLog


@dataclass(slots=True)
class BCCRAudit:
    """Stores BCCR synchronization audit log entries."""

    history: list[SynchronizationLog] = field(default_factory=list)

    def record(self, log: SynchronizationLog) -> None:
        self.history.append(log)
