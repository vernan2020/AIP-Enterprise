# IRRBB Phase 41 — NII Audit Physical Adapter Production Deployment Plan Contract

## Purpose

Phase 41 introduces a deterministic, immutable deployment-plan boundary for the NII audit physical persistence adapter.

The phase consumes the exact production-promotion authorization emitted by Phase 40 and turns it into a source-neutral deployment plan. It deliberately does **not** execute that plan.

## Architectural position

The production path now reads:

1. persistence readiness
2. persistence activation authorization
3. physical persistence activation
4. physical adapter certification
5. production readiness
6. production promotion authorization
7. production deployment plan

Phase 41 is therefore downstream from governance authorization but upstream from any future deployment-execution boundary.

## Domain contract

`NIIRunAuditPhysicalAdapterProductionDeploymentPlan` composes the exact Phase 40 `NIIRunAuditPhysicalAdapterProductionPromotionAuthorization` rather than copying its identities.

The plan adds only deployment-specific references:

- `plan_reference`
- `release_reference`
- `change_reference`
- `artifact_reference`
- `rollback_reference`
- ordered declarative deployment steps

Adapter identity, target environment and promotion authorization reference remain derived from the Phase 40 authorization.

## Deployment steps

A deployment step contains only:

- a positive integer `sequence`
- an `instruction_reference`

The instruction reference is an opaque reference to an externally governed runbook or instruction artifact. It is not a shell command, SQL statement, executable payload, credential, connection string or deployment script.

The service canonicalizes input steps by sequence and requires the resulting sequence to be contiguous from `1` through `N`.

Duplicate sequence numbers and duplicate instruction references are rejected.

## Fail-closed behavior

The plan service rejects:

- blank plan references
- blank release references
- blank change references
- blank artifact references
- blank rollback references
- an empty step collection
- duplicate sequence numbers
- duplicate instruction references
- non-contiguous step sequences

The immutable plan itself repeats these invariants so invalid state cannot be instantiated through direct construction without failing.

## Determinism

Callers may provide steps in arbitrary order. The service sorts them by their explicit sequence before constructing the plan.

This makes the resulting plan stable and reproducible while preserving caller-defined execution order.

## Explicit non-goals

Phase 41 does not implement or select:

- PostgreSQL or another physical database
- SQLAlchemy or another ORM
- Alembic or another migration runner
- DSNs or connection strings
- usernames, passwords, secrets, tokens or certificates
- infrastructure provisioning
- container or host deployment
- process startup
- runtime dependency-injection wiring
- deployment pipeline execution
- shell commands
- SQL execution
- remote connections
- rollback execution
- REST/API/UI integration
- human workflow execution
- external integrations blocked by Issue #66

## Security boundary

The deployment plan must remain safe to inspect, persist or audit because it contains references only. Secret material and executable instructions remain outside the domain object.

A later deployment-execution phase, if introduced, must consume this plan through a separate explicit boundary and must not silently reinterpret references as executable content.

## Relationship to Phase 40

Phase 40 answers:

> Is this exact READY production candidate explicitly authorized for promotion?

Phase 41 answers:

> What exact, immutable and auditable plan would a later deployment executor be allowed to follow for that authorization?

Neither phase performs the deployment itself.

## Issue #66

Issue #66 remains operationally blocked. Phase 41 does not invent, simulate, replace or bypass any external integration or historical source required by that issue.
