# IRRBB Phase 32 — NII Audit Schema Evolution Contract

## Purpose

Phase 32 defines a source-neutral schema-evolution contract for future physical implementations of `NIIRunAuditRepository`.

The objective is to make schema compatibility and migration paths explicit before any PostgreSQL, SQLAlchemy, migration framework or other physical persistence technology is selected.

## Scope

The phase introduces:

- `NIIAuditSchemaVersion`
- `NIIAuditSchemaMigrationStep`
- `NIIAuditSchemaEvolutionContract`
- `NIIAuditSchemaEvolutionService`

A schema contract declares:

1. the current schema version;
2. every version the adapter claims it can read;
3. every approved migration step between readable versions;
4. a traceable source reference for the contract and each migration step.

## Fail-closed invariants

- schema references are mandatory;
- versions are positive integers;
- a migration cannot cross logical schema references;
- migration steps must move forward to a higher version;
- the current version must be readable;
- all readable versions must belong to one logical schema;
- migration endpoints must themselves be declared readable;
- duplicate migration edges are rejected;
- an undeclared source version cannot be migrated;
- every declared readable historical version must have exactly one path to the current version;
- zero migration paths fail;
- multiple migration paths fail as ambiguous.

## Relationship with Phase 30

This contract supports the `SCHEMA_VERSIONING` and `MIGRATION_SAFETY` requirements introduced in Phase 30, but it does not itself certify those requirements.

A future physical adapter must still provide actual evidence that:

- stored records contain or otherwise resolve an unambiguous schema version;
- the declared migration implementation matches this contract;
- migration execution preserves data and audit integrity;
- rollback/recovery procedures are verified where institutionally required;
- the relevant Phase 30 evidence references are real and approved.

## Relationship with Phase 31

Phase 31 verifies repository behavior such as atomicity, idempotence, exact round-trip, integrity detection and recovery. Phase 32 adds the schema-evolution declaration needed to reason about persisted records across software versions.

Passing the Phase 31 conformance suite plus possessing a valid Phase 32 schema contract is still not sufficient to mark a physical adapter `READY`; Phase 30 remains the certification barrier.

## Explicit non-goals

Phase 32 does not implement:

- PostgreSQL or another physical database;
- SQLAlchemy models;
- Alembic or another migration engine;
- serialization/deserialization of `NIIRunAuditRecord`;
- actual migration code;
- runtime DI;
- REST/API/UI integration;
- retention, encryption or digital-signature policy;
- external IRRBB source adapters.

Issue #66 gates remain unchanged.
