# IRRBB Phase 30 — NII Audit Persistence Readiness Contract

## Objective

Define the source-neutral certification contract that any future physical repository must satisfy before it can be used to persist immutable NII audit records.

Phase 30 does not choose a database, ORM, deployment topology, or migration framework. It establishes the minimum auditable capabilities required by the domain boundary introduced in Phases 28–29.

## Required capabilities

A physical adapter is `READY` only when explicit evidence exists for every requirement:

1. `ATOMIC_PUT_IF_ABSENT` — insert-if-absent is atomic under concurrent writers.
2. `UNIQUE_RUN_REFERENCE` — `run_reference` uniqueness is enforced by the persistence mechanism, not only by application code.
3. `IMMUTABLE_RECORDS` — persisted audit records cannot be silently updated in place.
4. `ROUND_TRIP_SERIALIZATION` — specification, manifest and result survive serialize/deserialize without semantic substitution.
5. `SCHEMA_VERSIONING` — persisted representation carries an explicit schema/version contract.
6. `MIGRATION_SAFETY` — migrations preserve historical records or fail closed with an explicit incompatibility.
7. `TRANSACTIONAL_DURABILITY` — a successful write is durably committed; partial records are not exposed.
8. `READ_AFTER_WRITE_CONSISTENCY` — a successful write can be read back without substitution.
9. `INTEGRITY_VERIFICATION` — persisted content can be checked for integrity against its canonical audit payload.
10. `RECOVERY_VERIFICATION` — backup/restore or equivalent recovery is tested and preserves immutable audit semantics.

## Evidence model

Each requirement must be backed by a `NIIAuditPersistenceEvidence` carrying a nonblank `source_reference` to an executable test, certification artifact, architecture decision, migration verification, operational control, or equivalent evidence.

The readiness service does not infer capabilities from technology names. For example, selecting PostgreSQL does not by itself certify atomicity, immutability, recovery, or schema migration safety.

## Fail-closed semantics

`NIIAuditPersistenceReadinessService` returns:

- `READY` only when every canonical requirement is evidenced;
- `BLOCKED` when one or more requirements are missing, preserving the exact missing set;
- an error on duplicate evidence for the same requirement;
- an error on blank adapter or evidence references.

## Explicit non-scope

Phase 30 does not implement:

- PostgreSQL or another database adapter;
- SQLAlchemy models or migrations;
- runtime dependency injection;
- REST/API/UI integration;
- retention policy;
- digital signatures;
- source-specific IRRBB assumptions;
- any external-source integration blocked by Issue #66.

A future physical adapter must pass this readiness contract before being wired into the Phase 29 audited-run orchestration.
