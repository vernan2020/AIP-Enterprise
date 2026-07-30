from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Role:
    """Immutable role definition with inherited permissions."""

    name: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
    inherited_roles: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
