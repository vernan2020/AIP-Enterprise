from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class SnapshotVersion:
    """Immutable snapshot version represented as major/minor/patch."""

    major: int
    minor: int
    patch: int

    def next_patch(self) -> "SnapshotVersion":
        return SnapshotVersion(self.major, self.minor, self.patch + 1)

    def next_minor(self) -> "SnapshotVersion":
        return SnapshotVersion(self.major, self.minor + 1, 0)

    def next_major(self) -> "SnapshotVersion":
        return SnapshotVersion(self.major + 1, 0, 0)
