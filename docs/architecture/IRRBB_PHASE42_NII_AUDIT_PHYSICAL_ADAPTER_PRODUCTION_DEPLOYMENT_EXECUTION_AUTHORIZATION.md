# IRRBB Phase 42 — NII Audit Physical Adapter Production Deployment Execution Authorization

## Purpose

Phase 42 introduces the final domain authorization boundary immediately before any production deployment execution could occur.

It consumes one exact, immutable Phase 41 `NIIRunAuditPhysicalAdapterProductionDeploymentPlan` and produces a positive-only execution authorization only when every required last-mile evidence item is present.

Phase 42 does **not** execute deployment steps.

## Boundary

The Phase 42 aggregate is:

- `NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorization`

It composes the exact Phase 41 deployment plan and adds only:

- `execution_authorization_reference`
- canonical last-mile authorization evidence

Adapter, environment, promotion authorization, artifact and rollback identities are derived from the composed deployment plan rather than duplicated.

## Required last-mile evidence

Every execution authorization requires exactly one evidence item for each of the following categories:

1. `ARTIFACT_IDENTITY_VERIFIED`
2. `DEPLOYMENT_WINDOW_ACTIVE`
3. `EXECUTION_AUTHORITY_CONFIRMED`
4. `ROLLBACK_READINESS_CONFIRMED`
5. `PRE_DEPLOYMENT_CHECKPOINT_CONFIRMED`

Evidence is source-neutral and represented only by a requirement plus an opaque `source_reference`.

No credentials, commands, SQL, shell payloads or connection strings are allowed in this contract.

## Positive-only semantics

There is deliberately no partial or pending execution authorization.

`NIIRunAuditPhysicalAdapterProductionDeploymentExecutionAuthorizationService.authorize(...)` fails closed when:

- the execution authorization reference is blank;
- a requirement appears more than once;
- one or more required evidence categories are missing.

The service canonicalizes the evidence by requirement value and source reference before constructing the immutable authorization.

## Identity preservation

The authorization retains the exact Phase 41 deployment plan object. This prevents a deployment executor from receiving a newly reconstructed or partially equivalent plan.

Derived properties expose:

- deployment plan reference;
- adapter reference;
- target environment reference;
- Phase 40 promotion authorization reference;
- artifact reference;
- rollback reference.

These values remain governed by the already-certified Phase 38–41 chain.

## Explicitly not implemented

Phase 42 does not introduce:

- deployment execution;
- shell execution;
- SQL execution;
- PostgreSQL or another database;
- SQLAlchemy or ORM infrastructure;
- Alembic migrations;
- DSNs, passwords, tokens, certificates or secrets;
- infrastructure provisioning;
- runtime dependency-injection/startup wiring;
- CI/CD deployment jobs;
- rollback execution;
- REST/API/UI endpoints;
- human approval workflow execution;
- external data-source integration;
- any workaround for Issue #66.

## Architectural sequence

The production-persistence governance path is now:

`Phase 38 Technical Certification`
→ `Phase 39 Production Readiness`
→ `Phase 40 Promotion Authorization`
→ `Phase 41 Deployment Plan`
→ `Phase 42 Deployment Execution Authorization`

A future phase may introduce an execution receipt or execution-result contract, but any real deployment executor remains outside Phase 42.

## Safety invariant

Possession of a Phase 42 authorization proves only that one exact Phase 41 plan has passed the required last-mile governance checks.

It does not itself perform, schedule, trigger or confirm a deployment.
