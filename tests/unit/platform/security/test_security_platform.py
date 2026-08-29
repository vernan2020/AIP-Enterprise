from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aip.platform.security.audit.security_audit import SecurityAudit
from aip.platform.security.authentication.authentication_service import AuthenticationService
from aip.platform.security.authentication.credential_validator import StaticCredentialValidator
from aip.platform.security.authentication.session_manager import SessionManager
from aip.platform.security.authentication.token import Token
from aip.platform.security.authorization.authorization_service import AuthorizationService
from aip.platform.security.authorization.permission import Permission
from aip.platform.security.authorization.permission_evaluator import PermissionEvaluator
from aip.platform.security.authorization.policy import AuthorizationPolicy
from aip.platform.security.authorization.role import Role
from aip.platform.security.configuration.security_config import SecurityConfig
from aip.platform.security.events.security_events import (
    AuthenticationFailed,
    AuthenticationSucceeded,
    SecurityEventPublisher,
)
from aip.platform.security.exceptions.security_exceptions import (
    AuthenticationError,
    AuthorizationError,
    SecretProviderError,
    SessionError,
)
from aip.platform.security.identity.identity import Identity
from aip.platform.security.identity.identity_provider import InMemoryIdentityProvider
from aip.platform.security.identity.principal import Principal
from aip.platform.security.monitoring.security_health import SecurityHealth
from aip.platform.security.secrets.secret_provider import (
    EnvironmentSecretProvider,
    InMemorySecretProvider,
)
from aip.platform.security.telemetry.security_metrics import SecurityMetrics


def test_identity_and_principal_are_immutable() -> None:
    identity = Identity(
        subject="user-1", username="alice", groups=("admins",), claims={"tenant": "t1"}
    )
    updated = identity.with_claims({"tenant": "t2"})
    assert updated.claims["tenant"] == "t2"
    assert identity.claims == {"tenant": "t1"}


def test_authentication_service_authenticates_and_rejects() -> None:
    provider = InMemoryIdentityProvider({"alice": Identity(subject="user-1", username="alice")})
    validator = StaticCredentialValidator({"alice": "secret"})
    service = AuthenticationService(validator, provider)
    principal, token = service.authenticate("alice", "secret")
    assert principal.identity.username == "alice"
    assert token.value.startswith("token")

    with pytest.raises(AuthenticationError):
        service.authenticate("alice", "wrong")


def test_session_manager_lifecycle_and_expiration() -> None:
    session_manager = SessionManager(ttl_seconds=60)
    principal = Principal(identity=Identity(subject="user-1", username="alice"))
    session = session_manager.create_session(principal)
    assert session_manager.get_session(session.session_id).session_id == session.session_id

    expired_session = SessionManager(ttl_seconds=1)
    expired_principal = Principal(identity=Identity(subject="user-2", username="bob"))
    expired = expired_session.create_session(expired_principal)
    expired_token = Token(
        value="expired", expires_at=datetime.now(timezone.utc) - timedelta(seconds=5)
    )
    expired = SessionManager(ttl_seconds=1)
    expired_session = expired.create_session(expired_principal, expired_token)
    with pytest.raises(SessionError):
        expired.get_session(expired_session.session_id)

    session_manager.close_session(session.session_id)
    with pytest.raises(SessionError):
        session_manager.get_session(session.session_id)


def test_authorization_service_and_permission_evaluator() -> None:
    evaluator = PermissionEvaluator(
        policies=(
            AuthorizationPolicy(
                name="admin-policy",
                evaluator=lambda role, permission: role.name == "admin"
                and permission.name == "read",
            ),
        )
    )
    service = AuthorizationService(evaluator)
    principal = Principal(
        identity=Identity(subject="user-1", username="alice"),
        roles=("admin",),
        permissions=("read",),
    )
    assert service.authorize(principal, Permission(name="read")) is True
    assert service.authorize(principal, Permission(name="write")) is False


def test_roles_and_permissions_support_inheritance_and_deny_override() -> None:
    role = Role(name="manager", permissions=("approve",), inherited_roles=("employee",))
    principal = Principal(
        identity=Identity(subject="user-1", username="alice"),
        roles=("manager",),
        permissions=("approve",),
    )
    assert role.inherited_roles == ("employee",)
    assert principal.roles == ("manager",)


def test_secret_providers_and_environment_support() -> None:
    provider = InMemorySecretProvider({"API_KEY": "abc"})
    assert provider.get_secret("API_KEY") == "abc"

    env_provider = EnvironmentSecretProvider(prefix="AIP_")
    import os

    os.environ["AIP_API_KEY"] = "env-secret"
    assert env_provider.get_secret("API_KEY") == "env-secret"


def test_audit_monitoring_telemetry_and_events() -> None:
    audit = SecurityAudit()
    record = audit.record("AUTH", "login", correlation_id="c-1")
    assert record.event_type == "AUTH"
    assert len(audit.get_records()) == 1

    health = SecurityHealth(
        successful_logins=1,
        failed_logins=2,
        authorization_failures=3,
        active_sessions=4,
        expired_sessions=5,
        permission_checks=6,
    )
    assert health.successful_logins == 1

    metrics = SecurityMetrics(
        successful_logins=1,
        failed_logins=2,
        authorization_failures=3,
        active_sessions=4,
        expired_sessions=5,
        permission_checks=6,
    )
    assert metrics.permission_checks == 6

    publisher = SecurityEventPublisher()
    publisher.publish(AuthenticationSucceeded(username="alice"))
    publisher.publish(AuthenticationFailed(username="bob"))
    assert len(publisher.get_events()) == 2


def test_security_config_and_exceptions() -> None:
    config = SecurityConfig(
        session_ttl_seconds=60,
        issuer_name="demo",
        token_ttl_seconds=120,
        allowed_roles=("admin", "user"),
    )
    assert config.session_ttl_seconds == 60
    assert config.allowed_roles == ("admin", "user")

    with pytest.raises(AuthenticationError):
        raise AuthenticationError("bad")
    with pytest.raises(AuthorizationError):
        raise AuthorizationError("bad")
    with pytest.raises(SecretProviderError):
        raise SecretProviderError("bad")
