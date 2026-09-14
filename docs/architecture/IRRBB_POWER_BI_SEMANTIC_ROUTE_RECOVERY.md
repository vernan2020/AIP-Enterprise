# IRRBB / RTILB — Governed Power BI semantic-model route recovery

## Purpose

This slice restores the source-neutral Power BI route contract that was developed in historical Phase 18B but was not present in the certified release after the safe IRRBB/runtime integration.

The contract governs deployment-resolved routing for the two semantic-model sources already registered as IRRBB candidates:

- Credit: `Credito` / `coopealianza.credit.powerbi.credito`;
- Term deposits: `Certificados` / `coopealianza.liability.powerbi.certificados`.

This recovery does **not** connect to Power BI, authenticate to Microsoft, execute DAX, inspect rows, create canonical IRRBB positions, or activate either source in production runtime composition.

## Route contract

`PowerBISemanticModelRoute` contains only non-secret deployment references:

- `configuration_key`, which must match the governed physical-source descriptor;
- canonical non-nil `workspace_id` and `dataset_id` UUID values;
- `authentication_profile_key`, an opaque reference to an external authentication profile;
- the approved transport discriminator `EXECUTE_DAX_QUERIES_ARROW`.

The Power BI API origin is pinned by code to `https://api.powerbi.com`. Deployment configuration cannot replace the host with an arbitrary endpoint.

`InstitutionalPowerBISemanticRouteBinding` accepts only the exact governed Credit and Term Deposit descriptors and fails closed for lookalike descriptors, mismatched configuration keys, non-Power-BI sources, malformed identifiers, or non-opaque configuration/authentication references.

## Security and lineage boundary

The route and its `safe_reference` contain no token, password, client secret, refresh token, certificate, or other credential material. The route produces only a non-secret lineage reference of the form:

```text
<source_id>@powerbi://workspace/<workspace_id>/dataset/<dataset_id>
```

That reference proves only which governed deployment route was selected. It is not evidence that any semantic-model field exists and it does not upgrade source certification or calculation readiness.

## Relationship to Phase 20 and Issue #66

The certified release already contains the source-neutral semantic-model inspection/evidence contracts introduced after Phase 18B. Restoring this route boundary does not supply the institutional facts that those contracts require.

Issue #66 remains the external gate for Power BI. Production adapter work still requires the institutionally approved metadata-inspection mechanism, authentication mode, governed workspace/model identities, and real metadata-only evidence for `Credito` and `Certificados`.

No identifiers in this slice are institutional runtime identities. UUID values used in unit tests are synthetic test fixtures only and are never wired into runtime configuration.

## Explicit non-goals

This slice does not:

- introduce MSAL, requests, pyarrow, XMLA, ADOMD or another provider client;
- retrieve or cache credentials;
- perform HTTP requests or DAX queries;
- infer Power BI table/column mappings;
- mark any canonical requirement as available or ready;
- construct `BankingBookPosition` instances or cash-flow schedules;
- use ICL, SQL Server, or any alternate source as a fallback;
- alter GAP, EVE, NII, HQLA, VaR, DV01 or other financial methodology;
- change the fail-closed runtime composition required by Issue #66.

## Acceptance

The slice is admissible only if the exact candidate HEAD passes the standard release gates: Ruff, Black, mypy, compileall, unit tests, integration tests, coverage, package, runtime-source, pip-audit, Bandit, and Recovery Runtime Validation including Windows restore and certified package verification.
