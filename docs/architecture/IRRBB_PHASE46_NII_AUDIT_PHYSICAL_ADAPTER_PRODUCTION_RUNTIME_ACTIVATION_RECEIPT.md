# IRRBB Phase 46 — NII Audit Physical Adapter Production Runtime Activation Receipt

## Purpose

Phase 46 defines the immutable source-neutral receipt used to record what an external runtime-activation executor reports after attempting one exact Phase 45 production runtime activation authorization.

The receipt is observational only. It does not perform dependency wiring, adapter registration, application startup, health checks, rollback, infrastructure changes or any other side effect.

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

Phase 46 consumes and preserves by identity the exact immutable Phase 45 authorization.

## Domain contract

`NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceipt` contains:

- the exact `NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization`;
- a nonblank runtime activation receipt reference;
- a nonblank external activation reference;
- a derived overall activation status; and
- one canonical externally observed result for every required activation checkpoint.

Authorization, acceptance, deployment receipt, deployment execution, plan, adapter, environment, artifact and planned rollback identities are derived through the retained Phase 45 object rather than duplicated.

## Runtime activation checkpoints

The source-neutral checkpoint order is:

1. `DEPENDENCY_WIRING_APPLIED`;
2. `ADAPTER_REGISTRATION_CONFIRMED`;
3. `STARTUP_SEQUENCE_COMPLETED`; and
4. `RUNTIME_HEALTH_CONFIRMED`.

Each checkpoint result contains:

- the checkpoint identity;
- one status: `SUCCEEDED`, `FAILED` or `NOT_EXECUTED`; and
- one opaque nonblank evidence reference.

The receipt must contain each checkpoint exactly once and in the canonical operational order above.

## Derived activation status

The global runtime activation status is not caller-controlled.

It is derived deterministically:

- `SUCCEEDED` only when every checkpoint is `SUCCEEDED`;
- otherwise `FAILED`.

A directly constructed receipt whose supplied global status conflicts with its checkpoint results is invalid.

This design prevents a caller from reporting a successful global activation while any required checkpoint failed or was not executed.

## Service boundary

`NIIRunAuditPhysicalAdapterProductionRuntimeActivationReceiptService.record(...)`:

1. validates the receipt and activation references;
2. rejects duplicate checkpoint results;
3. rejects missing or unexpected checkpoints;
4. canonicalizes checkpoint results according to the explicit activation checkpoint order;
5. derives the overall activation status from checkpoint results; and
6. returns the immutable receipt.

The service records externally supplied observations only. It does not execute the activation attempt that those observations describe.

## Explicitly not implemented

Phase 46 deliberately does **not** implement:

- dependency-injection wiring;
- adapter or service registration;
- application, process, container or service startup/restart;
- runtime configuration mutation;
- runtime health-check execution;
- runtime activation execution;
- runtime deactivation;
- deployment execution;
- rollback execution;
- shell, PowerShell, SQL or operating-system commands;
- PostgreSQL or any other database;
- SQLAlchemy or ORM infrastructure;
- Alembic or schema execution;
- DSNs, credentials, tokens, certificates or secrets;
- network connectivity;
- infrastructure provisioning;
- CI/CD deployment or activation jobs;
- runtime dependency injection changes;
- REST/API/UI integration;
- external monitoring calls;
- human approval workflow execution; or
- any workaround for the external/historical integration blocked by Issue #66.

## Security invariant

Possession of a Phase 46 receipt proves only that an external actor or executor reported checkpoint outcomes for one exact Phase 45 authorization and that those reported outcomes satisfy the receipt invariants.

It does not prove that AIP itself performed dependency wiring, adapter registration, startup or health validation.

No executable command, credential, connection descriptor or infrastructure secret is embedded in the receipt.

## Architectural boundary

Phase 46 closes the observation boundary for a runtime activation attempt while keeping infrastructure outside the domain.

A later phase may define a positive-only runtime activation acceptance or operational handover gate. Such a phase must consume the exact Phase 46 receipt and must not reconstruct activation identity from loose string references.
