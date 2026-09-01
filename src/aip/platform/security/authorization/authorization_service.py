from __future__ import annotations

from aip.platform.security.authorization.permission import Permission
from aip.platform.security.authorization.permission_evaluator import PermissionEvaluator
from aip.platform.security.authorization.role import Role
from aip.platform.security.identity.principal import Principal


class AuthorizationService:
    """Service for authorization decisions using an evaluator and role map."""

    def __init__(self, evaluator: PermissionEvaluator | None = None) -> None:
        self._evaluator = evaluator or PermissionEvaluator()

    def authorize(self, principal: Principal, permission: Permission) -> bool:
        return self._evaluator.evaluate(principal, permission)

    def add_role(self, principal: Principal, role: Role) -> Principal:
        roles = tuple(sorted(set(principal.roles + (role.name,))))
        return Principal(
            identity=principal.identity,
            roles=roles,
            permissions=principal.permissions,
            claims=principal.claims,
        )
