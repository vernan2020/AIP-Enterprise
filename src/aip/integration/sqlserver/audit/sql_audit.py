from __future__ import annotations

from dataclasses import dataclass, field

from aip.integration.audit.synchronization_log import SynchronizationLog


@dataclass(slots=True)
class SQLAudit:
    """Stores SQL synchronization audit entries."""

    entries: list[SynchronizationLog] = field(default_factory=list)

    def record(self, log: SynchronizationLog) -> None:
        self.entries.append(log)
