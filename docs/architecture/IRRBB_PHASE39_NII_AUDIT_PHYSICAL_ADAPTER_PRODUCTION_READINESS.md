# IRRBB Phase 39 — NII Audit Physical Adapter Production Readiness

## Objective

Phase 39 adds a source-neutral production-readiness contract for one physical NII audit persistence adapter that has already obtained the Phase 38 technical certification bundle.

The phase separates two concerns that must not be conflated:

- **technical adapter certification** — established by Phase 38; and
- **target-environment production readiness** — assessed by Phase 39.

A READY Phase 39 assessment is still not a production promotion authorization and does not deploy or activate infrastructure.

## Composition

`NIIRunAuditPhysicalAdapterProductionReadinessAssessment` contains:

- the exact `NIIRunAuditPhysicalAdapterCertificationBundle` from Phase 38;
- one explicit `environment_reference`;
- a READY or BLOCKED status;
- certified and missing production-readiness requirements;
- canonical traceable evidence references, one per certified requirement.

The adapter identity is derived from the certification bundle. Phase 39 does not copy adapter/schema/codec/integrity/repository identities into parallel fields, preventing drift from the already certified chain.

## Required production-readiness evidence

The source-neutral requirement set is:

1. `TARGET_ENVIRONMENT_IDENTIFIED`;
2. `CONNECTIVITY_VALIDATED`;
3. `ACCESS_CONTROL_VALIDATED`;
4. `SECRET_HANDLING_VALIDATED`;
5. `ENCRYPTION_VALIDATED`;
6. `SCHEMA_CHANGE_PATH_VALIDATED`;
7. `BACKUP_RESTORE_PATH_VALIDATED`;
8. `OBSERVABILITY_VALIDATED`;
9. `CAPACITY_VALIDATED`;
10. `ROLLBACK_PATH_VALIDATED`.

These are evidence categories, not implementation instructions. No database engine, cloud platform, credential mechanism, monitoring vendor or deployment tool is selected here.

## Assessment service

`NIIRunAuditPhysicalAdapterProductionReadinessService.assess(...)` receives:

- the exact Phase 38 certification bundle;
- a nonblank target-environment reference; and
- explicit evidence objects.

The service rejects duplicate evidence for the same requirement, canonicalizes evidence ordering, calculates the complete requirement partition and returns:

- `READY` only when every requirement is evidenced; or
- `BLOCKED` when one or more requirements are missing.

No evidence is inferred. An empty evidence set produces a BLOCKED assessment covering all requirements as missing.

## Evidence handling

`NIIRunAuditPhysicalAdapterProductionEvidence` stores only:

- the requirement identifier; and
- an opaque `source_reference`.

Phase 39 deliberately does not store secret values, credentials, connection strings, tokens, certificates or infrastructure payloads. Those remain external to the domain object and may only be referenced through auditable source identities.

## Fail-closed invariants

The assessment is structurally valid only when:

1. the target environment reference is nonblank;
2. certified and missing requirement sets do not overlap;
3. certified plus missing requirements cover the full mandatory requirement set;
4. every certified requirement has exactly one evidence item;
5. evidence ordering is canonical;
6. READY has no missing requirements; and
7. BLOCKED has at least one missing requirement.

## Important semantics

A READY Phase 39 assessment means:

> the technically certified adapter candidate has explicit evidence for every production-readiness capability required by this domain boundary for one named target environment.

It does **not** mean:

- approved for production;
- deployed to production;
- runtime-wired;
- credentials exposed to the application;
- database migrations executed;
- infrastructure selected by the domain;
- human change approval completed;
- Issue #66 resolved.

## Explicit non-goals

Phase 39 does not implement or select:

- PostgreSQL or another database;
- SQLAlchemy or another ORM;
- Alembic or physical migrations;
- DSNs, passwords, tokens or certificates;
- connection pools;
- infrastructure provisioning;
- network changes;
- runtime dependency injection;
- startup wiring;
- deployment execution;
- REST/API/UI integration;
- human approval workflows;
- external data-source adapters blocked by Issue #66.

## Resulting chain

The controlled path is now:

`persistence readiness + serialization compatibility`

→ `Phase 36 persistence activation authorization`

→ `Phase 37 exact physical adapter activation`

→ `Phase 38 technical physical adapter certification bundle`

→ `Phase 39 target-environment production readiness assessment`

A subsequent phase may consume a READY Phase 39 assessment plus explicit governance authorization to create a production-promotion capability. That authorization must remain separate from readiness and must not silently deploy infrastructure.
