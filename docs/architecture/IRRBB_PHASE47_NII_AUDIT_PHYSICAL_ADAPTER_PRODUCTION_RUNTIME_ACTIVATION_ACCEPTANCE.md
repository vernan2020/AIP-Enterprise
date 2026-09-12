# IRRBB Phase 47 — NII Audit Physical Adapter Production Runtime Activation Acceptance

## Purpose

Phase 47 defines the immutable positive-only acceptance boundary for one exact successful Phase 46 production runtime activation receipt.

The phase records governance acceptance only after runtime activation has been externally reported as successful and the required operational evidence is complete. It does not activate runtime components, perform health checks, query observability systems, transfer ownership or execute support workflows.

## Position in the production sequence

The production-side sequence is now:

1. Phase 38 — Physical Adapter Certification Bundle.
2. Phase 39 — Physical Adapter Production Readiness.
3. Phase 40 — Production Promotion Authorization.
4. Phase 41 — Production Deployment Plan.
5. Phase 42 — Production Deployment Execution Authorization.
6. Phase 43 — Production Deployment Execution Receipt.
7. Phase 44 — Production Post-Execution Acceptance.
8. Phase 45 — Production Runtime Activation Authorization.
9. Phase 46 — Production Runtime Activation Receipt.
10. Phase 47 — Production Runtime Activation Acceptance.

Phase 47 consumes the exact immutable Phase 46 receipt and preserves it by identity.

## Domain contract

`NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptance` contains:

- the exact `NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt`;
- a nonblank acceptance reference; and
- one canonical evidence item for every required runtime-acceptance control.

Runtime activation, authorization, post-execution acceptance, deployment receipt, execution, plan, adapter, environment, artifact and rollback identities are derived through the retained Phase 46 object rather than duplicated.

## Required evidence

Runtime activation acceptance requires all of the following source-neutral controls:

- `ACTIVATION_RECEIPT_VERIFIED`;
- `RUNTIME_STABILITY_VALIDATED`;
- `OBSERVABILITY_VALIDATED`;
- `OPERATIONS_OWNERSHIP_ACCEPTED`; and
- `SUPPORT_HANDOVER_CONFIRMED`.

Each evidence item contains only an opaque nonblank source reference. Evidence references point to externally governed records and do not embed commands, credentials, monitoring queries or runtime configuration.

## Positive-only semantics

Phase 47 has no pending, partial or blocked acceptance object.

Acceptance exists only when:

1. the exact Phase 46 receipt has overall status `SUCCEEDED`;
2. every retained Phase 46 checkpoint result is `SUCCEEDED`;
3. the acceptance reference is nonblank;
4. every required acceptance control has exactly one evidence item; and
5. evidence is canonicalized deterministically.

Any failed or non-executed runtime checkpoint, incomplete evidence, duplicate requirement or blank reference fails closed.

Possession of a Phase 47 acceptance proves only that the exact successful activation receipt had the required governance evidence recorded. It does not prove that AIP itself performed activation, stability validation, observability checks or operational handover.

## Service boundary

`NIIRunAuditPhysicalAdapterProductionRuntimeActivationAcceptanceService.accept(...)`:

1. requires Phase 46 overall status `SUCCEEDED`;
2. fail-closed revalidates every activation checkpoint as `SUCCEEDED`;
3. validates the acceptance reference;
4. rejects duplicate acceptance requirements;
5. rejects missing or unexpected acceptance requirements;
6. canonicalizes evidence by requirement and source reference; and
7. returns the immutable positive-only acceptance.

The service performs no side effects.

## Explicitly not implemented

Phase 47 deliberately does **not** implement:

- runtime activation execution;
- dependency-injection wiring;
- adapter or service registration;
- process, service or application startup/restart;
- runtime configuration mutation;
- health-check execution;
- observability or monitoring queries;
- alert acknowledgement;
- operations ownership transfer execution;
- support handover workflow execution;
- runtime deactivation;
- deployment or rollback execution;
- shell, PowerShell, SQL or operating-system commands;
- PostgreSQL or any other database;
- SQLAlchemy or ORM infrastructure;
- Alembic or schema execution;
- DSNs, credentials, tokens, certificates or secrets;
- network connectivity;
- infrastructure provisioning;
- CI/CD activation jobs;
- REST/API/UI integration;
- external integrations; or
- any workaround for the external/historical integration blocked by Issue #66.

## Architectural boundary

Phase 47 closes the source-neutral governance sequence for accepting an externally reported runtime activation. A later phase may model operational handover confirmation, steady-state service ownership, or a physical runtime adapter boundary, but it must consume the exact Phase 47 acceptance instead of rebuilding identity from loose references.
