# IRRBB Phase 57 — NII Audit Operational Status Re-Attestation Contract

## Purpose

Phase 57 introduces a new operational status attestation specifically bound to the post-recovery continuity epoch created by Phase 56.

Phase 49 attests the initial steady-state operations record created by Phase 48. After intervention, recovery, acceptance, and creation of a distinct Phase 56 continuity epoch, that original attestation must not be reused as if it described the new epoch.

Phase 57 therefore creates an immutable re-attestation for one exact Phase 56 continuity epoch while preserving the existing operational status vocabulary.

## Status vocabulary

Phase 57 reuses `NIIRunAuditPhysicalAdapterProductionOperationalStatus` from Phase 49:

- `HEALTHY`
- `DEGRADED`
- `UNAVAILABLE`

No second status enum is introduced.

## Composition boundary

`NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation` retains the exact `NIIRunAuditPhysicalAdapterProductionOperationalContinuityEpoch` by identity.

The retained chain remains traceable through:

`Previous Steady State -> Prior Status Attestation -> Intervention -> Recovery -> Recovery Acceptance -> Continuity Epoch -> Status Re-Attestation`

The aggregate exposes opaque derived references through that chain without copying or reconstructing prior aggregates.

## Continuity-epoch precondition

The retained Phase 56 continuity epoch must:

- have a nonblank `epoch_reference`;
- have an `epoch_reference` distinct from its `previous_operations_reference`.

Phase 57 defensively revalidates those identity conditions to fail closed against malformed or bypassed upstream objects.

## Required evidence

Exactly one source-neutral evidence item is required for each control:

1. `CONTINUITY_EPOCH_VERIFIED`
2. `OBSERVABILITY_STATUS_VERIFIED`
3. `INCIDENT_STATUS_VERIFIED`
4. `CONTINUITY_STATUS_VERIFIED`
5. `CHANGE_STATUS_VERIFIED`

Each evidence item carries a nonblank opaque `source_reference`.

Duplicate, missing, unexpected, or noncanonical evidence is rejected.

## Exception semantics

Phase 57 preserves the Phase 49 exception model:

- `HEALTHY` must contain no exception references;
- `DEGRADED` requires at least one exception reference;
- `UNAVAILABLE` requires at least one exception reference.

Exception references must be nonblank, unique, and canonically sorted.

## Service behavior

`NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestationService.attest(...)`:

1. requires one exact valid Phase 56 continuity epoch;
2. validates the re-attestation reference;
3. rejects duplicate or incomplete evidence;
4. canonicalizes evidence order;
5. canonicalizes exception references;
6. returns one immutable status re-attestation.

The service has no side effects.

## Distinction from Phase 49

Phase 49 is bound to the original Phase 48 steady-state operations record.

Phase 57 is bound to a distinct Phase 56 continuity epoch created after accepted recovery. The Phase 49 attestation remains historical evidence and is exposed through `previous_attestation_reference`; it is not mutated, replaced, or reinterpreted as current post-recovery status.

## Explicit non-goals

Phase 57 does **not** implement:

- health-check execution;
- observability or monitoring queries;
- metric collection;
- incident detection;
- alert acknowledgement;
- incident workflow execution;
- `RESUME` or `REACTIVATE` execution;
- process, service, application, or container startup/restart;
- runtime activation or deactivation;
- dependency-injection or provider switching;
- runtime configuration or environment mutation;
- operational ownership transfer execution;
- continuity or failover execution;
- deployment or rollback execution;
- PostgreSQL, database, SQLAlchemy, ORM, or Alembic operations;
- DSNs, credentials, tokens, certificates, or secrets;
- shell, PowerShell, SQL, or operating-system commands;
- network connectivity;
- infrastructure provisioning;
- CI/CD operational-status jobs;
- REST, API, or UI integration;
- external integrations;
- any workaround for blocked Issue #66.

## Security invariant

Possession of a Phase 57 re-attestation proves only that one exact Phase 56 continuity epoch has a complete, source-neutral operational-status evidence set satisfying the declared classification and exception invariants.

It does not prove that AIP executed health checks, queried monitoring, detected incidents, changed runtime state, started services, or independently verified infrastructure health.

## Next safe boundary

A subsequent phase may introduce a post-recovery **Operational Intervention Authorization Gate** bound to a Phase 57 re-attestation, allowing the continuity epoch to re-enter the governed intervention lifecycle without reusing an authorization tied to the original Phase 49 attestation.
