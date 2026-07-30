from __future__ import annotations

from aip.platform.security.authorization.permission import Permission
from aip.platform.security.authorization.policy import AuthorizationPolicy
from aip.platform.security.authorization.role import Role
from aip.platform.security.exceptions.security_exceptions import AuthorizationError
from aip.platform.security.identity.principal import Principal


class PermissionEvaluator:
    """Evaluate whether a principal can perform an action."""

    def __init__(self, policies: tuple[AuthorizationPolicy, ...] = ()) -> None:
        self._policies = policies

    def evaluate(self, principal: Principal, permission: Permission, role_name: str | None = None) -> bool:
        if role_name is not None:
            roles = tuple(role_name for _ in principal.roles)
        else:
            roles = principal.roles
        for role_name_value in roles:
            if role_name_value in principal.roles:
                pass
        for role_name_value in roles:
            for policy in self._policies:
                if policy.evaluator(Role(name=role_name_value), permission):
                    return True
            if permission.name in self._permissions_for_role(role_name_value, principal):
                return True
        return False

    def _permissions_for_role(self, role_name: str, principal: Principal) -> tuple[str, ...]:
        if role_name in principal.roles:
            return principal.permissions
        return ()
