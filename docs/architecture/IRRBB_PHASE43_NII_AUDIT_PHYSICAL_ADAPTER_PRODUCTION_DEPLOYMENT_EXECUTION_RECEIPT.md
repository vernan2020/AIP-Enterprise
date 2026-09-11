# IRRBB Phase 43 — NII Audit Physical Adapter Production Deployment Execution Receipt

## Purpose

Phase 43 defines the immutable domain receipt produced after an external deployment executor reports the observed result of executing one exact Phase 42 production deployment execution authorization.

This phase records outcome evidence only. It does not execute deployment steps, invoke rollback, connect to infrastructure or introduce a production executor.

## Position in the activation sequence

The production-side sequence is now:

1. Phase 38 — Physical Adapter Certification Bundle.
2. Phase 39 — Physical Adapter Production Readiness.
3. Phase 40 — Production Promotion Authorization.
4. Phase 41 — Production Deployment Plan.
5. Phase 42 — Production Deployment Execution Authorization.
6. Phase 43 — Production Deployment Execution Receipt.

Phase 43 therefore consumes the exact authorization object produced by Phase 42 and preserves that object by identity.

## Domain contract

`NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceipt` contains:

- the exact `NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization`;
- a nonblank receipt reference;
- a nonblank external execution reference;
- a derived overall execution status;
- one canonical result for every deployment-plan step;
- an observed rollback status; and
- a nonblank rollback evidence reference.

Adapter, target environment, plan, artifact and planned rollback identities are derived from the retained Phase 42 authorization rather than duplicated.

## Step-result semantics

Every authorized deployment-plan step must have exactly one result identified by its plan sequence.

Supported step states are:

- `SUCCEEDED`;
- `FAILED`; and
- `NOT_EXECUTED`.

Each result also carries a nonblank opaque evidence reference supplied by the external execution boundary. The domain contract does not interpret that reference and does not contain executable commands.

The receipt must cover the exact step-sequence set of the retained Phase 41 plan. Results are stored in canonical plan order. Missing, unexpected or duplicate step sequences fail closed.

## Overall execution status

The overall execution status is derived rather than supplied by callers:

- `SUCCEEDED` only when every authorized plan step succeeded;
- `FAILED` when any plan step failed or was not executed.

A successful execution may only report rollback status `NOT_REQUIRED`.

## Rollback status

Rollback is represented independently from the deployment execution result because a failed deployment may still have a successful rollback.

Supported rollback states are:

- `NOT_REQUIRED`;
- `NOT_ATTEMPTED`;
- `SUCCEEDED`; and
- `FAILED`.

The receipt always carries a rollback evidence reference so that the observed rollback disposition remains externally traceable without embedding rollback instructions in the domain model.

## Service boundary

`NIIRunAuditPhysicalAdapterProductionDeploymentExecutionReceiptService.record(...)`:

1. validates receipt, execution and rollback evidence references;
2. rejects duplicate step-result sequences;
3. verifies exact coverage of the authorized deployment plan;
4. canonicalizes step results by plan sequence;
5. derives the overall execution status from step results;
6. validates the success/rollback consistency rule; and
7. returns an immutable receipt.

The service does not call an executor and does not perform any side effects.

## Explicitly not implemented

Phase 43 deliberately does **not** implement:

- deployment execution;
- shell, SQL or operating-system commands;
- an executor adapter;
- PostgreSQL or any other database;
- SQLAlchemy or ORM infrastructure;
- Alembic or schema execution;
- DSNs, credentials, tokens, certificates or secrets;
- infrastructure provisioning;
- deployment pipelines;
- runtime dependency-injection/startup wiring;
- rollback execution;
- REST/API/UI integration;
- human approval workflow execution; or
- any workaround for the external/historical integration blocked by Issue #66.

## Architectural boundary

Phase 43 is an observation and audit boundary. It proves what an external executor reported for an already authorized plan, but it does not prove that AIP itself can deploy or roll back a physical persistence adapter.

A future physical execution adapter must remain outside this domain contract and translate infrastructure-specific execution output into these source-neutral receipt types.
