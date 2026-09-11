# IRRBB Phase 45 — NII Audit Physical Adapter Production Runtime Activation Authorization

## Purpose

Phase 45 defines the immutable governance authorization required before a production physical adapter may be activated in application runtime after one exact successful Phase 44 post-execution acceptance.

This phase authorizes only. It does not perform dependency wiring, start services, register adapters, mutate runtime configuration or connect to infrastructure.

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

Phase 45 consumes the exact immutable Phase 44 acceptance object and preserves it by identity.

## Domain contract

`NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorization` contains:

- the exact `NIIRunAuditPhysicalAdapterProductionPostExecutionAcceptance`;
- a nonblank activation authorization reference; and
- one canonical evidence item for every required runtime-activation control.

Acceptance, receipt, execution, plan, adapter, environment, artifact and rollback identities are derived through the retained Phase 44 object rather than duplicated.

## Required evidence

Runtime activation authorization requires all of the following source-neutral controls:

- `POST_EXECUTION_ACCEPTANCE_VERIFIED`;
- `RUNTIME_CONFIGURATION_APPROVED`;
- `DEPENDENCY_WIRING_APPROVED`;
- `STARTUP_SEQUENCE_APPROVED`; and
- `OPERATIONS_ACTIVATION_AUTHORITY_CONFIRMED`.

Each evidence item contains only an opaque nonblank source reference. The domain does not embed executable configuration, commands, credentials or infrastructure instructions.

## Positive-only semantics

Phase 45 has no partial, pending or conditionally authorized state.

Authorization exists only when:

1. one exact Phase 44 acceptance is retained;
2. the activation authorization reference is nonblank;
3. every required activation control has exactly one evidence item; and
4. evidence is stored in canonical order.

Missing, unexpected or duplicate evidence fails closed.

Possession of a Phase 45 authorization proves that the accepted deployment passed the required governance checks for a future runtime activation. It does not prove that runtime activation has occurred.

## Service boundary

`NIIRunAuditPhysicalAdapterProductionRuntimeActivationAuthorizationService.authorize(...)`:

1. validates the authorization reference;
2. rejects duplicate activation requirements;
3. rejects missing or unexpected activation requirements;
4. canonicalizes evidence by requirement and source reference; and
5. returns the immutable positive-only authorization.

The service does not perform side effects.

## Explicitly not implemented

Phase 45 deliberately does **not** implement:

- runtime activation;
- dependency-injection wiring changes;
- container or service registration;
- process, service or application startup/restart;
- runtime configuration mutation;
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
- REST/API/UI integration;
- external monitoring calls;
- human approval workflow execution; or
- any workaround for the external/historical integration blocked by Issue #66.

## Architectural boundary

Phase 45 is the final governance authorization immediately before any future runtime-activation boundary. A later phase may model a runtime activation receipt or activation adapter, but that infrastructure must remain outside this domain contract and must consume the exact Phase 45 authorization rather than reconstructing its identity from loose references.
