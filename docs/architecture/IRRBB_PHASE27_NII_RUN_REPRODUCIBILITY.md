# IRRBB Phase 27 — NII Run Reproducibility / Evidence Manifest

## Objective

Phase 27 adds a deterministic, source-neutral reproducibility identity for one approved NII methodology perimeter. It does not persist runs, authorize sources or introduce new financial assumptions.

## Design

`NIIRunReproducibilityService` converts `NIIMethodologyRunSpecification` into a canonical JSON payload and computes SHA-256 over that exact UTF-8 representation.

The canonical payload includes:

- methodology code, version, governance status, source reference and effective date;
- valuation date and horizon end date;
- balance-sheet assumption and shock timing;
- projection-basis source reference;
- reporting currency;
- ordered stressed-scenario set;
- canonicalized policy references;
- canonicalized evidence references;
- reproducibility schema version.

`run_reference` is intentionally excluded from the fingerprint. It identifies an execution instance, while the fingerprint identifies the methodological perimeter. Therefore two separate executions using the same approved perimeter produce the same fingerprint.

Policy and evidence references are sorted before canonical serialization because their tuple order is not a financial assumption. The stressed-scenario order remains significant because Phase 25/26 explicitly preserve requested scenario order.

## Manifest contract

`NIIRunEvidenceManifest` stores:

- execution `run_reference`;
- schema version;
- SHA-256 specification fingerprint;
- canonical payload;
- canonical policy references;
- canonical evidence references.

The manifest validates its fingerprint against the canonical payload and rejects tampering.

## Fail-closed properties

- Changing methodology, horizon, projection basis, currency, balance-sheet assumption, shock timing, stressed scenarios or references changes the methodological identity.
- Reordering policy/evidence references alone does not change identity.
- Reordering stressed scenarios does change identity.
- A manifest with a fingerprint that does not reconcile to its canonical payload is invalid.
- No source content is invented or hashed unless it is explicitly part of the approved run specification.

## Explicitly outside Phase 27

- persistence or database schemas;
- digital signatures or approval workflows;
- file-content hashing of external evidence;
- runtime/API/UI integration;
- physical source adapters;
- scenario selection defaults;
- forward curves, replacement assumptions or behavioral models;
- closing any Issue #66 external-source gate.
