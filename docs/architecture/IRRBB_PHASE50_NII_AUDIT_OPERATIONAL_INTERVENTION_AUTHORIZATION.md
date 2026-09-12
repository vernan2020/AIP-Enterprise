# IRRBB Phase 50 — NII Audit Operational Intervention Authorization

## Purpose

Phase 50 defines a source-neutral, positive-only authorization for one explicit operational intervention against an exact Phase 49 non-healthy status attestation.

It governs authorization only. It does not execute suspension, deactivation, restart, recovery, rollback, failover, connection changes or infrastructure commands.

## Position in the production sequence

Phase 50 consumes the exact `NIIRunAuditPhysicalAdapterProductionOperationalStatusAttestation` created in Phase 49. Adapter, environment, artifact, runtime activation and steady-state identities remain derived through that immutable chain rather than being resupplied as loose values.

## Actions

The authorization action must be supplied explicitly as one of:

- `SUSPEND`;
- `DEACTIVATE`.

Phase 50 deliberately does not infer an action from operational status. Both `DEGRADED` and `UNAVAILABLE` may be evaluated for either action when governance evidence supports that decision. `HEALTHY` status cannot authorize an intervention.

## Required evidence

Every authorization requires exactly one source-neutral evidence item for:

- `STATUS_ATTESTATION_VERIFIED`;
- `INTERVENTION_POLICY_VERIFIED`;
- `OPERATIONAL_APPROVAL_VERIFIED`; and
- `CONTINUITY_IMPACT_VERIFIED`.

Evidence references are opaque, nonblank and canonicalized deterministically. Missing or duplicate evidence fails closed.

## Service boundary

`NIIRunAuditPhysicalAdapterProductionOperationalInterventionAuthorizationService.authorize(...)`:

1. retains the exact Phase 49 attestation;
2. rejects `HEALTHY` status;
3. requires a nonblank authorization reference;
4. requires the intervention action explicitly;
5. validates complete and unique evidence coverage;
6. canonicalizes the evidence; and
7. returns an immutable positive-only authorization.

The service has no side effects.

## Fail-closed semantics

No default intervention action exists. No mapping such as `DEGRADED -> SUSPEND` or `UNAVAILABLE -> DEACTIVATE` is embedded in the domain. No authorization object exists for a healthy service or for incomplete governance evidence.

## Explicit non-goals

Phase 50 does **not** implement:

- suspension or deactivation execution;
- runtime mutation;
- process termination or restart;
- database disconnect or failover;
- credential or secret handling;
- incident creation, paging or escalation;
- remediation or recovery execution;
- rollback execution;
- REST/API/UI integration;
- runtime dependency injection;
- PostgreSQL, SQLAlchemy or migrations;
- external source integrations; or
- any workaround for Issue #66.

## Next safe boundary

A later phase may define an execution receipt or operational intervention acceptance contract that consumes the exact Phase 50 authorization. Such a phase must not infer, expand or substitute the authorized action and must remain separate from actual infrastructure commands until a concrete runtime implementation is explicitly certified.
