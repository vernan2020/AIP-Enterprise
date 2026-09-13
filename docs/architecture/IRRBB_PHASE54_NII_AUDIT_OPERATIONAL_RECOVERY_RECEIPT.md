# IRRBB Phase 54 — NII Audit Operational Recovery Execution Receipt Contract

## Purpose

Phase 54 records, as an immutable domain receipt, the externally observed outcome of one exact Phase 53 operational recovery authorization.

The contract covers return-to-service actions already governed by Phase 53:

- `RESUME`, paired with a previously accepted `SUSPEND` intervention;
- `REACTIVATE`, paired with a previously accepted `DEACTIVATE` intervention.

Phase 54 does not execute either action. It only records evidence reported by an external executor.

## Composition boundary

`NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceipt` retains the exact `NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization` object by identity.

This preserves the complete governance chain:

`Intervention Acceptance -> Recovery Authorization -> Recovery Receipt`

The receipt also exposes derived opaque references back through the intervention and steady-state chain without copying or reconstituting prior domain objects.

## Required checkpoints

Every receipt must contain exactly one result for each checkpoint, in canonical order:

1. `AUTHORIZATION_ACKNOWLEDGED`
2. `RECOVERY_ACTION_APPLIED`
3. `TARGET_STATE_VERIFIED`
4. `CONTINUITY_CONTROL_CONFIRMED`

Each checkpoint result has one status:

- `SUCCEEDED`
- `FAILED`
- `NOT_EXECUTED`

and a nonblank opaque `evidence_reference`.

## Derived overall status

The overall receipt status is not caller-controlled.

It is derived deterministically:

- `SUCCEEDED` only when all required checkpoints are `SUCCEEDED`;
- `FAILED` when any checkpoint is `FAILED` or `NOT_EXECUTED`.

The aggregate validates that the stored status matches the retained checkpoint results.

## Service behavior

`NIIRunAuditPhysicalAdapterProductionOperationalRecoveryReceiptService.record(...)`:

1. validates nonblank receipt and recovery references;
2. rejects duplicate checkpoints;
3. rejects missing or unexpected checkpoints;
4. canonicalizes checkpoint order;
5. derives the overall status;
6. returns one immutable receipt.

The service has no side effects.

## Explicit non-goals

Phase 54 does **not** implement:

- `RESUME` execution;
- `REACTIVATE` execution;
- process, service, application, or container startup/restart;
- runtime activation or deactivation;
- dependency-injection or provider switching;
- runtime configuration or environment mutation;
- health-check execution;
- monitoring or observability queries;
- incident workflow execution;
- continuity or failover execution;
- deployment or rollback execution;
- PostgreSQL, database, SQLAlchemy, ORM, or Alembic operations;
- DSNs, credentials, tokens, certificates, or secrets;
- shell, PowerShell, SQL, or operating-system commands;
- network connectivity;
- infrastructure provisioning;
- CI/CD recovery jobs;
- REST, API, or UI integration;
- external integrations;
- any workaround for blocked Issue #66.

## Security invariant

Possession of a Phase 54 receipt proves only that an external executor reported checkpoint outcomes for one exact Phase 53 authorization and that those outcomes were normalized under this domain contract.

It does not prove that AIP itself changed runtime state, started a service, switched a provider, queried live monitoring, or performed recovery.

## Next safe boundary

A subsequent phase may introduce a positive-only **Operational Recovery Acceptance Gate** that accepts only one exact successful Phase 54 receipt with complete post-recovery governance evidence.
