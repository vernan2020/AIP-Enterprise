from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class Identity:
    """Immutable identity information for a principal."""

    subject: str
    username: str
    display_name: str | None = None
    email: str | None = None
    groups: tuple[str, ...] = field(default_factory=tuple)
    claims: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def with_claims(self, claims: dict[str, Any]) -> "Identity":
        return Identity(
            subject=self.subject,
            username=self.username,
            display_name=self.display_name,
            email=self.email,
            groups=self.groups,
            claims=dict(claims),
            created_at=self.created_at,
        )
