# IRRBB Phase 18B — Governed Power BI semantic-model route

## Purpose

Phase 18B defines the deployment-resolved route contract required to inspect the two institutional Power BI semantic models already registered as candidate RTILB physical sources:

- Credit: `Credito` / `coopealianza.credit.powerbi.credito`;
- Term deposits: `Certificados` / `coopealianza.liability.powerbi.certificados`.

This slice does not connect to Power BI and does not claim that either semantic model is sufficient for RTILB. It only establishes the boundary that a future metadata inspector/transport must satisfy before any model table or column can be observed.

## Existing configuration boundary

The Phase 16 physical source descriptor deliberately stores an opaque `configuration_key`, not a URL, workspace ID, dataset ID or credential.

AIP also already separates:

- ordinary application configuration through the infrastructure configuration layer; and
- secret retrieval through `SecretProvider` implementations.

Phase 18B preserves those boundaries. Runtime/deployment code may resolve a semantic-model route from the descriptor's configuration key, but the IRRBB route contract never stores a credential or bearer token.

## Route contract

`PowerBISemanticModelRoute` contains only:

- `configuration_key` — must equal the governed physical-source descriptor key;
- `workspace_id` — canonical, non-nil UUID;
- `dataset_id` — canonical, non-nil UUID;
- `authentication_profile_key` — opaque reference to an external authentication profile;
- the approved transport discriminator.

The approved transport is currently:

```text
EXECUTE_DAX_QUERIES_ARROW
```

No alternate host or arbitrary URL is part of the route.

## Endpoint pinning

The route constructs the semantic query endpoint only from the fixed Microsoft Power BI API origin:

```text
https://api.powerbi.com/v1.0/myorg/groups/<workspace_id>/datasets/<dataset_id>/executeDaxQueries
```

This is a deliberate security boundary. A manipulated deployment route cannot replace the API origin with another host while preserving the same typed contract.

The endpoint and `safe_reference` contain no authentication-profile key, secret or bearer token.

## Authentication boundary

`authentication_profile_key` is an opaque configuration reference. It is not:

- a client secret;
- a bearer token;
- a password;
- a tenant credential;
- an embedded JSON credential;
- a URL.

A future authentication adapter may resolve that reference through the platform security/configuration boundary. Phase 18B does not choose an identity mechanism and does not introduce MSAL, requests, pyarrow, ADOMD or XMLA dependencies.

## Institutional source binding

`InstitutionalPowerBISemanticRouteBinding` accepts only the exact governed Phase 16 semantic source descriptors:

```text
CREDIT_SEMANTIC_MODEL_SOURCE
TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE
```

A descriptor with the same source ID/kind/segment but altered metadata is rejected. A workbook or portfolio source is rejected. The route's `configuration_key` must exactly match the chosen descriptor.

This prevents an arbitrary semantic model from entering the IRRBB source path merely because its technology is Power BI.

## Safe lineage

A successful binding can emit a route-level non-secret reference:

```text
<source_id>@powerbi://workspace/<workspace_id>/dataset/<dataset_id>
```

This reference identifies the deployment route for diagnostics. It is not source-data evidence and must not be used as proof that any canonical IRRBB field exists.

## Fail-closed invariants

1. Only the exact institutional Credit and Term Deposit semantic-model descriptors can bind.
2. `configuration_key` must match the descriptor exactly.
3. Workspace and dataset identifiers must be canonical, non-nil UUIDs.
4. Configuration/authentication references must be opaque keys, not URLs or free-form credential material.
5. The Power BI API origin is fixed by code, not supplied by deployment configuration.
6. Only the approved semantic query transport is accepted.
7. Route binding provides no source certification status.
8. Route binding provides no table, column, row or contractual-field evidence.

## Explicit exclusions

Phase 18B does not:

- authenticate to Microsoft Entra ID;
- obtain or cache tokens;
- make HTTP calls;
- add an HTTP/Arrow/XMLA dependency;
- execute DAX;
- inspect tables or columns;
- select model entities;
- infer aliases;
- define CREDIT or LIABILITY source requirement profiles;
- mark any requirement `NATIVE_AVAILABLE`, `DERIVABLE_WITH_DOCUMENTED_RULE` or `READY`;
- create `BankingBookPosition` records;
- construct cash-flow schedules;
- use ICL or `VISTA_1514_1515_1516` as fallback sources;
- modify GAP, EVE, NII or scenario calculations;
- wire Power BI into production runtime composition.

## Next safe slice

The next Power BI slice may define a metadata-inspection port and fixed metadata-query contract for the governed route. The physical transport must remain separate from IRRBB business mapping and must fail closed on query or authorization errors.

Only after actual metadata from `Credito` and `Certificados` is captured may a later source-evidence phase propose mappings to canonical RTILB requirements.
