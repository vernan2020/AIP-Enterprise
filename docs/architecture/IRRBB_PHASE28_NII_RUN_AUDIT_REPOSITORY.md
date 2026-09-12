# IRRBB Phase 28 — NII Run Audit Repository Boundary

## Objective

Phase 28 introduces a source-neutral persistence boundary for immutable audited NII methodology runs. It does not select a database or implement a physical adapter.

The persisted domain record is:

```text
NIIMethodologyRunSpecification
        +
NIIRunEvidenceManifest
        +
NIIMethodologyRunResult
        ↓
NIIRunAuditRecord
```

The boundary preserves the exact methodology perimeter and the exact result that was produced under that perimeter.

## Domain contract

`NIIRunAuditRecord` binds:

- the Phase 26 `NIIMethodologyRunSpecification`;
- the Phase 27 `NIIRunEvidenceManifest`;
- the Phase 26 `NIIMethodologyRunResult`.

Construction fails closed when the manifest or result substitutes the run specification identity. Before persistence or after retrieval, `NIIRunAuditService` rebuilds the Phase 27 manifest from the specification and requires exact equality with the stored manifest.

## Repository port

`NIIRunAuditRepository` exposes only:

```python
get_by_run_reference(*, run_reference)
put_if_absent(*, record)
```

`put_if_absent` is intentionally atomic at the port boundary. A physical adapter must implement the uniqueness guarantee on `run_reference` without a read-then-write race.

There is no update or delete operation in Phase 28.

## Write semantics

The service defines these outcomes:

- `STORED`: the run reference did not exist and the exact record was inserted;
- `IDEMPOTENT`: the exact same immutable record already existed;
- conflict: the run reference already existed with any different immutable audit payload.

A conflict is explicit. No existing audit record may be overwritten.

If the existing record has a different methodology fingerprint, the conflict identifies that the methodological perimeter differs. If the fingerprint is identical but the result or other bound audit payload differs, the write also conflicts.

## Fingerprint cardinality

The Phase 27 specification fingerprint is not a globally unique run identifier.

Two different `run_reference` values may legitimately have the same fingerprint when the same approved methodology perimeter is executed more than once. Therefore:

```text
unique execution key = run_reference
methodology identity = specification_fingerprint
```

A future storage adapter must not impose a uniqueness constraint on `specification_fingerprint` alone.

## Fail-closed repository behavior

The service rejects a repository implementation that:

- substitutes a different `run_reference` on lookup or write;
- reports `created=True` but returns a record different from the submitted record;
- returns a stored record whose manifest no longer reconciles to its specification.

These checks prevent a storage implementation from silently weakening the domain audit contract.

## Explicitly out of scope

Phase 28 does **not** implement:

- PostgreSQL or another persistence technology;
- ORM entities or migrations;
- API or UI integration;
- mutable audit records;
- deletion/retention policy;
- digital signatures;
- external file-content hashing;
- physical IRRBB source adapters;
- institutional scenario or behavioral defaults.

No external-source evidence gate tracked by Issue #66 is crossed by this phase.

## Next boundary

A later slice may implement a physical audit repository only after its operational persistence requirements are approved. That adapter must preserve the atomic insert-if-absent and immutability semantics defined here.
