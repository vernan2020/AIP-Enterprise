# IRRBB Phase 29 — NII Audited Run Orchestration

## Objective

Phase 29 composes the previously certified NII methodology-run, reproducibility, and immutable audit-storage boundaries into one source-neutral orchestration service.

The orchestration sequence is:

`NIIMethodologyRunSpecification`
→ existing-run lookup
→ methodology execution when absent
→ deterministic reproducibility manifest
→ immutable `NIIRunAuditRecord`
→ atomic audit repository write.

No institutional source mapping, persistence technology, runtime wiring, API, or UI behavior is introduced in this phase.

## New service

`NIIAuditedRunService` is the domain orchestration boundary for one governed NII run.

For a new `run_reference` it:

1. confirms that no immutable audit record already exists;
2. delegates all financial evaluation to `NIIMethodologyRunService`;
3. builds the deterministic Phase 27 `NIIRunEvidenceManifest`;
4. binds specification, manifest and result into a Phase 28 `NIIRunAuditRecord`;
5. persists it through `NIIRunAuditService` and the source-neutral `NIIRunAuditRepository` port.

The orchestration service does not calculate interest, project positions, choose scenarios, select policies, or infer missing contractual data.

## Historical replay semantics

An existing run is never recalculated merely because the same request is submitted again.

If the repository contains the same `run_reference` and the exact same `NIIMethodologyRunSpecification`, the service returns the persisted record with `NIIRunAuditWriteStatus.IDEMPOTENT` without invoking projection strategies or reading calculation sources again.

This is intentional. A historical run is an immutable fact. Re-running it against data or capabilities that may have changed after the original execution would weaken auditability.

If the same `run_reference` already exists with a different methodology run specification, the service raises `NIIRunAuditConflictError` before any NII recalculation occurs.

## Concurrency

The initial lookup is an optimization and a replay guard, not the final concurrency control.

A concurrent writer may create the same run after the lookup and before persistence. The Phase 28 repository boundary therefore remains authoritative through atomic `put_if_absent` semantics. The audit service accepts an exact concurrent duplicate as idempotent and rejects a conflicting payload.

## Failure atomicity

A methodology execution failure does not create a partial audit record.

The manifest and immutable record are created only after `NIIMethodologyRunService.execute(...)` returns a complete `NIIMethodologyRunResult`. Persistence occurs only after that binding succeeds.

## Explicit non-goals

Phase 29 does not add:

- PostgreSQL, SQLAlchemy, migrations or physical repository adapters;
- runtime dependency injection;
- REST endpoints or UI integration;
- digital signatures;
- external evidence-file content hashes;
- retention or archival policies;
- source-specific NII projection strategies;
- institutional assumptions or fallback data sources.

Issue #66 external-source gates remain unchanged.

## Tested invariants

Unit tests verify that:

- a new run executes once and persists a complete immutable audit bundle;
- replay of the exact same run returns the stored record without recalculation;
- a reused `run_reference` with a different specification conflicts before recalculation;
- execution failure leaves the audit repository unchanged.

## Safe next boundary

A later phase may introduce a physical audit repository adapter only after its storage technology, transaction model, schema, migration policy, operational ownership and retention requirements are approved. That adapter must implement the existing Phase 28 port rather than weakening the immutable domain semantics defined here.
