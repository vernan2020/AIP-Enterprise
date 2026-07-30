from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.platform.security.identity.identity import Identity


@dataclass(frozen=True, slots=True)
class Principal:
    """Immutable security principal representing an authenticated entity."""

    identity: Identity
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    claims: dict[str, Any] = field(default_factory=dict)
