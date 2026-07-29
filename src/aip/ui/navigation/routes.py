from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Route:
    id: str
    label: str
    icon: str = ""
    parent: str | None = None
