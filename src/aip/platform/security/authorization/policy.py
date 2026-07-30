from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from aip.platform.security.authorization.permission import Permission
from aip.platform.security.authorization.role import Role


@dataclass(frozen=True, slots=True)
class AuthorizationPolicy:
    """A simple authorization policy for RBAC evaluation."""

    name: str
    evaluator: Callable[[Role, Permission], bool] = field(default=lambda role, permission: False)
