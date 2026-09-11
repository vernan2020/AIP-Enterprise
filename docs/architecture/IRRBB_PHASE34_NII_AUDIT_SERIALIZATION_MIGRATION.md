# IRRBB Phase 34 — NII Audit Serialization Migration / Decode Orchestration

## Objective

Phase 34 adds a source-neutral orchestration boundary for consuming historical NII audit serialization envelopes through the explicit schema migration paths introduced in Phase 32 and the serialization envelope introduced in Phase 33.

The phase does not choose or implement a database, ORM, serialization format, migration engine, cryptographic algorithm, or physical adapter.

## Scope

The implementation adds:

- `NIIRunAuditPayloadMigrationTransformer`
- `NIIRunAuditPayloadMigrationTransformerResolver`
- `NIIRunAuditAppliedSerializationMigration`
- `NIIRunAuditSerializationMigrationResult`
- `NIIRunAuditSerializationMigrationService`

The service consumes a historical `NIIRunAuditSerializationEnvelope`, resolves the unique declared migration path with `NIIAuditSchemaEvolutionService`, applies one explicit transformer per approved migration step, rebuilds integrity metadata after every step, and finally delegates decoding of the current-schema envelope to `NIIRunAuditSerializationService`.

## Fail-closed invariants

1. The historical envelope payload is integrity-verified before any transformer is resolved or executed.
2. The envelope integrity reference must exactly match the supplied integrity boundary.
3. Migration paths are never inferred by this service; only the unique path declared by Phase 32 is accepted.
4. Each resolved transformer must declare exactly the same `NIIAuditSchemaMigrationStep` requested by the migration path.
5. Transformer references are mandatory and nonblank.
6. A transformer may not return an empty payload.
7. Every migrated payload receives a new integrity digest before the next step.
8. The run reference is preserved across every generated envelope.
9. The final envelope must reach the contract's exact current schema version.
10. Final decoding is delegated to Phase 33, retaining its codec reference, schema support, integrity and decoded run-reference checks.

## Audit evidence

Every applied migration produces `NIIRunAuditAppliedSerializationMigration`, containing:

- the exact approved schema migration step;
- the explicit transformer reference;
- the source payload digest;
- the target payload digest.

This provides a deterministic audit trail of how a historical serialized record was transformed before decoding.

## Current-schema behavior

If the incoming envelope already uses the current schema version, the Phase 32 migration path is empty. No transformer is resolved or executed. The original envelope is decoded directly through Phase 33 and the applied migration evidence tuple is empty.

## Explicit non-goals

Phase 34 does not implement or mandate:

- PostgreSQL or another database;
- SQLAlchemy or another ORM;
- Alembic or another migration engine;
- JSON, MessagePack, protobuf or another payload format;
- SHA-256 or another production integrity algorithm;
- digital signatures or encryption;
- key management;
- physical migration execution against stored rows;
- runtime dependency injection;
- REST/API/UI integration;
- external integrations blocked by Issue #66.

## Relationship with prior phases

- Phase 30 remains the persistence readiness certification barrier.
- Phase 31 remains the repository behavior conformance boundary.
- Phase 32 defines readable schema versions and the unique migration path.
- Phase 33 defines the serialization envelope plus codec and integrity boundaries.
- Phase 34 orchestrates explicit payload migration and current-schema decoding while preserving those boundaries.
