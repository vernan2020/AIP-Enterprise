# ADR — IRRBB Power BI authentication gate

**Status:** Accepted  
**Date:** 2026-09-17  
**Scope:** IRRBB configured Power BI semantic-model metadata inspection  
**External gate:** GitHub Issue #66

## Context

The governed Power BI metadata path is implemented through
`ConfiguredPowerBISemanticMetadataSnapshotFetcher` and the existing
`PowerBIAccessTokenProvider` port. Route configuration contains only non-secret
dataset/workspace identifiers and an opaque `authentication_profile_key`.

The repository does not contain an approved institutional OAuth/MSAL, service
principal, delegated-user, managed-identity, Windows-integrated, or other Power BI
token-acquisition implementation that can be reused without making an institutional
security assumption.

## Decision

Power BI token acquisition remains an external institutional responsibility.

`build_configured_semantic_model_inspection_coordinator` must continue to require an
explicit `PowerBIAccessTokenProvider`. No default provider, environment-variable
token reader, command-line token parameter, plaintext file reader, embedded client
secret, refresh-token cache, certificate path, or interactive login flow may be added
as a fallback.

The production HTTP transport may have a default because it is stateless and pinned
to the Microsoft Power BI API origin. Credential acquisition may not have a default.

Credential acquisition must occur only when metadata inspection is executed. Merely
constructing the coordinator must not read credentials or contact an identity
provider.

## Required evidence before implementing a concrete provider

A provider-specific authentication slice may start only after the institution
confirms, through the approved security/deployment channel:

1. the approved authentication mode;
2. the approved identity or application registration pattern;
3. the permitted Power BI/Fabric API scopes or application permissions;
4. the approved secret/certificate/token storage and retrieval mechanism;
5. the token lifetime/refresh policy;
6. whether interactive authentication is prohibited or permitted;
7. the runtime ownership model for `authentication_profile_key`;
8. the deployment environments in which the provider is authorized.

Credentials, access tokens, refresh tokens, client secrets, certificates and similar
secret material must never be committed to this repository or posted in Issue #66.

## Runtime boundary

Once an institutional provider is approved and implemented, the existing metadata
adapter remains constrained to:

- the governed route selected for the exact registered IRRBB source;
- `https://api.powerbi.com/v1.0/myorg/`;
- dataset identity validation before metadata queries;
- the metadata-only `INFO.VIEW.*` projections already implemented;
- no contractual rows, balances or position extraction;
- `schema_freshness=UNKNOWN` until independently certified;
- no canonical Credit/Captaciones mapping or RTILB production activation from the
  authentication slice alone.

## Consequences

The metadata path is intentionally non-runnable against live Power BI until an
institutionally approved token provider is injected. This is a required fail-closed
state, not a missing fallback.

A regression test protects the no-default-authentication invariant so a future change
cannot silently introduce a credential strategy through composition.
