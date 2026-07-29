from __future__ import annotations

from dataclasses import dataclass, field

from aip.integration.audit.synchronization_log import SynchronizationLog


@dataclass(slots=True)
class FolderAudit:
    """Stores folder watch audit entries."""

    entries: list[SynchronizationLog] = field(default_factory=list)

    def record(self, log: SynchronizationLog) -> None:
        self.entries.append(log)
