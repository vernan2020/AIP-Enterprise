from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SnapshotCreated:
    """Domain event emitted when a market snapshot is created."""

    snapshot_id: str
