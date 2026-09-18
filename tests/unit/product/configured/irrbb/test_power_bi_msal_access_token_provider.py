from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from aip.infrastructure.configuration.models import (
    PowerBIAuthenticationProfileConfiguration,
    Settings,
)
from aip.product.configured.irrbb.power_bi_msal_access_token_provider import (
    ConfiguredMSALPowerBIAccessTokenProvider,
)

_PROFILE_KEY = "security.auth.power_bi.readonly"
_CLIENT_ID = "12345678-1234-4234-8234-1234567890ab"
_TENANT_ID = "22345678-1234-4234-8234-1234567890ab"
_SCOPE = "https://analysis.windows.net/powerbi/api/Dataset.Read.All"


class _FakeMSALClient:
    def __init__(
        self,
        *,
        accounts: list[Mapping[str, Any]] | None = None,
        silent_results: list[Mapping[str, Any] | None] | None = None,
        interactive_result: Mapping[str, Any] | None = None,
    ) -> None:
        self.accounts = accounts or []
        self.silent_results = list(silent_results or [])
        self.interactive_result = interactive_result or {"access_token": "interactive-token"}
        self.interactive_calls = 0
        self.silent_calls = 0

    def get_accounts(self) -> list[Mapping[str, Any]]:
        return list(self.accounts)

    def acquire_token_silent(
        self,
        scopes: list[str],
        *,
        account: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        assert scopes == [_SCOPE]
        assert account in self.accounts
        self.silent_calls += 1
        if not self.silent_results:
            return None
        return self.silent_results.pop(0)

    def acquire_token_interactive(self, scopes: list[str]) -> Mapping[str, Any]:
        assert scopes == [_SCOPE]
        self.interactive_calls += 1
        return self.interactive_result


class _Factory:
    def __init__(self, client: _FakeMSALClient) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def __call__(self, *, client_id: str, authority: str) -> _FakeMSALClient:
        self.calls.append((client_id, authority))
        return self.client


def _profile(
    *,
    client_id: str = _CLIENT_ID,
    tenant_id: str = _TENANT_ID,
    scopes: tuple[str, ...] = (_SCOPE,),
) -> PowerBIAuthenticationProfileConfiguration:
    return PowerBIAuthenticationProfileConfiguration(
        client_id=client_id,
        tenant_id=tenant_id,
        scopes=scopes,
    )


def test_settings_default_to_no_power_bi_authentication_profiles() -> None:
    settings = Settings()

    assert settings.irrbb.power_bi_authentication_profiles == {}


def test_authentication_profile_contains_no_secret_material_fields() -> None:
    assert set(PowerBIAuthenticationProfileConfiguration.model_fields) == {
        "client_id",
        "tenant_id",
        "scopes",
    }


def test_authentication_profile_rejects_blank_identity_references() -> None:
    with pytest.raises(ValidationError):
        PowerBIAuthenticationProfileConfiguration(
            client_id="   ",
            tenant_id=_TENANT_ID,
        )

    with pytest.raises(ValidationError):
        PowerBIAuthenticationProfileConfiguration(
            client_id=_CLIENT_ID,
            tenant_id="   ",
        )


def test_provider_prefers_silent_token_and_does_not_prompt() -> None:
    account = {"home_account_id": "account-1"}
    client = _FakeMSALClient(
        accounts=[account],
        silent_results=[{"access_token": "silent-token"}],
    )
    factory = _Factory(client)
    provider = ConfiguredMSALPowerBIAccessTokenProvider(
        {_PROFILE_KEY: _profile()},
        client_factory=factory,
    )

    token = provider.require_access_token(authentication_profile_key=_PROFILE_KEY)

    assert token == "silent-token"
    assert client.silent_calls == 1
    assert client.interactive_calls == 0
    assert factory.calls == [
        (_CLIENT_ID, f"https://login.microsoftonline.com/{_TENANT_ID}")
    ]


def test_provider_falls_back_to_interactive_pkce_flow_when_cache_misses() -> None:
    account = {"home_account_id": "account-1"}
    client = _FakeMSALClient(
        accounts=[account],
        silent_results=[None],
        interactive_result={"access_token": "interactive-token"},
    )
    provider = ConfiguredMSALPowerBIAccessTokenProvider(
        {_PROFILE_KEY: _profile()},
        client_factory=_Factory(client),
    )

    token = provider.require_access_token(authentication_profile_key=_PROFILE_KEY)

    assert token == "interactive-token"
    assert client.silent_calls == 1
    assert client.interactive_calls == 1


def test_provider_fails_closed_for_unknown_profile() -> None:
    provider = ConfiguredMSALPowerBIAccessTokenProvider({})

    with pytest.raises(KeyError, match="No Power BI authentication profile configured"):
        provider.require_access_token(authentication_profile_key=_PROFILE_KEY)


def test_provider_rejects_noncanonical_profile_key() -> None:
    with pytest.raises(ValueError, match="profile key must be non-blank"):
        ConfiguredMSALPowerBIAccessTokenProvider(
            {f" {_PROFILE_KEY} ": _profile()}
        )


def test_provider_rejects_noncanonical_uuid_identifiers() -> None:
    with pytest.raises(ValueError, match="client_id must be a canonical UUID string"):
        ConfiguredMSALPowerBIAccessTokenProvider(
            {_PROFILE_KEY: _profile(client_id=_CLIENT_ID.upper())}
        )


def test_provider_rejects_overprivileged_or_unapproved_scopes() -> None:
    with pytest.raises(ValueError, match="only delegated Dataset.Read.All"):
        ConfiguredMSALPowerBIAccessTokenProvider(
            {
                _PROFILE_KEY: _profile(
                    scopes=(
                        _SCOPE,
                        "https://analysis.windows.net/powerbi/api/Dataset.ReadWrite.All",
                    )
                )
            }
        )


def test_provider_rejects_interactive_result_without_token() -> None:
    client = _FakeMSALClient(
        interactive_result={"error": "interaction_required"},
    )
    provider = ConfiguredMSALPowerBIAccessTokenProvider(
        {_PROFILE_KEY: _profile()},
        client_factory=_Factory(client),
    )

    with pytest.raises(RuntimeError, match="did not return an access token"):
        provider.require_access_token(authentication_profile_key=_PROFILE_KEY)


def test_provider_reuses_same_msal_client_within_process() -> None:
    client = _FakeMSALClient(
        interactive_result={"access_token": "interactive-token"},
    )
    factory = _Factory(client)
    provider = ConfiguredMSALPowerBIAccessTokenProvider(
        {_PROFILE_KEY: _profile()},
        client_factory=factory,
    )

    assert provider.require_access_token(authentication_profile_key=_PROFILE_KEY)
    assert provider.require_access_token(authentication_profile_key=_PROFILE_KEY)

    assert len(factory.calls) == 1
