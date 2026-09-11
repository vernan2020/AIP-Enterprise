# IRRBB Phase 31 — NII Audit Repository Conformance Suite

## Objective

Phase 31 adds an executable, source-neutral conformance suite for future physical implementations of `NIIRunAuditRepository`.

The suite does **not** select or implement PostgreSQL, SQLAlchemy, DuckDB, files, cloud storage, or any other persistence technology. It verifies observable repository behavior before a physical adapter can be considered eligible for production certification.

## Relationship with Phase 30

Phase 30 defines the complete persistence-readiness requirements. Phase 31 verifies only the subset that can be exercised through the repository contract plus explicit test-harness lifecycle hooks.

Passing Phase 31 is therefore **necessary but not sufficient** for Phase 30 `READY` status.

Phase 30 requirements that still require adapter-specific evidence include, among others:

- schema versioning;
- migration safety;
- transactional durability under infrastructure failure;
- operational backup/restore controls beyond a repository reopen;
- production deployment and recovery evidence.

## Executable checks

`NIIAuditRepositoryConformanceSuite` executes eight isolated checks:

1. `FIRST_WRITE`
   - first `put_if_absent` must create the exact submitted record.
2. `IDEMPOTENT_REPEAT`
   - exact repetition must not create a second record and must return the persisted record.
3. `UNIQUE_RUN_REFERENCE`
   - a conflicting payload with the same `run_reference` must preserve and return the first persisted record.
4. `ROUND_TRIP`
   - a persisted audit record must deserialize/reconstruct into an equal domain record.
5. `READ_AFTER_WRITE`
   - a successful write must be immediately visible through the repository read contract.
6. `ATOMIC_CONCURRENT_PUT_IF_ABSENT`
   - two concurrent writers for the same `run_reference` must produce exactly one creator and both responses must converge on the same persisted record.
7. `RECOVERY_REOPEN`
   - reopening the repository against the same backing store must recover the persisted record without rebuilding it from in-memory domain objects.
8. `INTEGRITY_DETECTION`
   - controlled corruption outside the repository API must not be returned as valid data; reads must fail with `NIIAuditRepositoryIntegrityError`.

## Conformance harness

A physical adapter supplies `NIIAuditRepositoryConformanceHarness` only for certification tests. It must provide:

- `reset()` — creates an empty isolated backing store for the next check;
- `repository()` — opens the repository against the current test store;
- `reopen_repository()` — reconnects to the same store;
- `corrupt_persisted_record()` — alters persisted state outside the domain repository API.

This keeps database lifecycle, connection management, storage format and fault injection outside the domain repository port.

## Fail-closed behavior

The suite never converts a failed behavior into a warning. Every check is reported explicitly in `NIIAuditRepositoryConformanceResult` as passed or failed.

A result is conformant only when all executable checks pass.

The suite also rejects invalid fixtures before execution:

- the conflicting record must reuse the primary `run_reference`;
- the conflicting record must differ from the primary record;
- the secondary record must use a different `run_reference`.

## Concurrency invariant

The concurrency test rejects last-writer-wins behavior.

For two competing records sharing one `run_reference`:

- exactly one response may report `created=True`;
- the persisted record must be one of the submitted records;
- both repository responses must return that exact persisted record.

This is the executable form of the atomic insert-if-absent invariant required by the audited-run orchestration.

## Integrity invariant

A repository that silently returns corrupted persisted audit data is non-conformant.

Physical adapters must implement an integrity mechanism appropriate to their storage design. Phase 31 intentionally does not prescribe hashes, signatures, checksums, database constraints, or serialization formats.

## Explicit non-goals

Phase 31 does not implement:

- a PostgreSQL adapter;
- SQLAlchemy models;
- database migrations;
- runtime dependency injection;
- REST/API/UI integration;
- retention or archival policy;
- digital signatures;
- encryption policy;
- source adapters blocked by Issue #66.

## Activation rule

No future physical `NIIRunAuditRepository` should be connected to the audited NII runtime merely because it satisfies the Python protocol.

The adapter must first:

1. pass the Phase 31 conformance suite;
2. provide the remaining Phase 30 certification evidence;
3. pass exact-SHA CI and security gates;
4. be activated explicitly through runtime composition in a later approved phase.
