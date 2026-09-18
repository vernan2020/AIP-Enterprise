from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import msal

_POWER_BI_DATASET_READ_SCOPE = (
    "https://analysis.windows.net/powerbi/api/Dataset.Read.All"
)
_ENTRA_AUTHORITY_BASE = "https://login.microsoftonline.com"


class PowerBIAuthenticationProfileSource(Protocol):
    """Non-secret public-client configuration required for delegated authentication."""

    client_id: str
    tenant_id: str
    scopes: Sequence[str]


class MSALPublicClient(Protocol):
    """Narrow MSAL public-client port used by the configured token provider."""

    def get_accounts(self) -> list[Mapping[str, Any]]: ...

    def acquire_token_silent(
        self,
        scopes: list[str],
        *,
        account: Mapping[str, Any],
    ) -> Mapping[str, Any] | None: ...

    def acquire_token_interactive(
        self,
        scopes: list[str],
    ) -> Mapping[str, Any]: ...


class MSALPublicClientFactory(Protocol):
    """Factory boundary so authentication behavior remains unit-testable."""

    def __call__(
        self,
        *,
        client_id: str,
        authority: str,
    ) -> MSALPublicClient: ...


@dataclass(frozen=True, slots=True)
class PowerBIDelegatedAuthenticationProfile:
    """Validated, non-secret identity route for one delegated Power BI profile."""

    client_id: UUID
    tenant_id: UUID
    scopes: tuple[str, ...]


def _default_msal_client_factory(
    *,
    client_id: str,
    authority: str,
) -> MSALPublicClient:
    return msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
    )


class ConfiguredMSALPowerBIAccessTokenProvider:
    """Acquire short-lived delegated Power BI tokens through MSAL.

    The provider is deliberately public-client only: no password, client secret,
    certificate private key or refresh token is accepted as configuration. It attempts
    silent acquisition from the in-process MSAL cache first and falls back to MSAL's
    interactive browser flow when no suitable token is available.

    Cross-process token persistence is intentionally out of scope here; adding it
    requires an institutionally approved encrypted cache strategy.
    """

    def __init__(
        self,
        profiles_by_key: Mapping[str, PowerBIAuthenticationProfileSource],
        *,
        client_factory: MSALPublicClientFactory | None = None,
    ) -> None:
        profiles: dict[str, PowerBIDelegatedAuthenticationProfile] = {}
        for profile_key, configuration in profiles_by_key.items():
            self._validate_profile_key(profile_key)
            profiles[profile_key] = self._build_profile(configuration)
        self._profiles_by_key = profiles
        self._client_factory = client_factory or _default_msal_client_factory
        self._clients_by_key: dict[str, MSALPublicClient] = {}

    def require_access_token(self, *, authentication_profile_key: str) -> str:
        """Return a validated access token without exposing authentication material."""

        self._validate_profile_key(authentication_profile_key)
        try:
            profile = self._profiles_by_key[authentication_profile_key]
        except KeyError as exc:
            raise KeyError(
                f"No Power BI authentication profile configured for "
                f"{authentication_profile_key!r}"
            ) from exc

        client = self._client(authentication_profile_key, profile)
        scopes = list(profile.scopes)

        for account in client.get_accounts():
            result = client.acquire_token_silent(scopes, account=account)
            token = _optional_access_token(result)
            if token is not None:
                return token

        result = client.acquire_token_interactive(scopes)
        return _required_access_token(result)

    def _client(
        self,
        profile_key: str,
        profile: PowerBIDelegatedAuthenticationProfile,
    ) -> MSALPublicClient:
        cached = self._clients_by_key.get(profile_key)
        if cached is not None:
            return cached
        client = self._client_factory(
            client_id=str(profile.client_id),
            authority=f"{_ENTRA_AUTHORITY_BASE}/{profile.tenant_id}",
        )
        self._clients_by_key[profile_key] = client
        return client

    @staticmethod
    def _build_profile(
        configuration: PowerBIAuthenticationProfileSource,
    ) -> PowerBIDelegatedAuthenticationProfile:
        client_id = _required_uuid("Power BI authentication client_id", configuration.client_id)
        tenant_id = _required_uuid("Power BI authentication tenant_id", configuration.tenant_id)
        scopes = tuple(str(scope).strip() for scope in configuration.scopes)

        if scopes != (_POWER_BI_DATASET_READ_SCOPE,):
            raise ValueError(
                "Power BI authentication profile must request only delegated Dataset.Read.All"
            )

        return PowerBIDelegatedAuthenticationProfile(
            client_id=client_id,
            tenant_id=tenant_id,
            scopes=scopes,
        )

    @staticmethod
    def _validate_profile_key(profile_key: str) -> None:
        if not profile_key or profile_key != profile_key.strip():
            raise ValueError("Power BI authentication profile key must be non-blank")


def _required_uuid(field_name: str, value: str) -> UUID:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a canonical UUID string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a canonical UUID string") from exc
    if str(parsed) != value.casefold():
        raise ValueError(f"{field_name} must be a canonical UUID string")
    return parsed


def _optional_access_token(result: Mapping[str, Any] | None) -> str | None:
    if result is None:
        return None
    token = result.get("access_token")
    if token is None:
        return None
    return _validate_access_token(token)


def _required_access_token(result: Mapping[str, Any]) -> str:
    token = result.get("access_token")
    if token is None:
        raise RuntimeError("Power BI delegated authentication did not return an access token")
    return _validate_access_token(token)


def _validate_access_token(token: Any) -> str:
    if not isinstance(token, str) or not token.strip() or token != token.strip():
        raise ValueError("MSAL returned a malformed Power BI access token")
    return token
