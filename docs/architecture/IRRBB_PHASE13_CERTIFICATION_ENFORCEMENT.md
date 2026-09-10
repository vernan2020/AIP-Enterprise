# IRRBB / RTILB — Phase 13 Certification Enforcement

## 1. Purpose

Phase 13 turns the source-certification result introduced in Phase 11 and exercised against the institutional investment master in Phase 12 into an executable ingestion gate.

The objective is narrow: a physical source record must not cross the source anti-corruption layer into a canonical `BankingBookPosition` unless the source snapshot has a `READY` certification report.

This phase does not select or compose a physical production source. It does not make the institutional investment master `READY`, and it does not resolve any source gap identified in Phase 12.

## 2. Architectural boundary

```text
Physical source snapshot
        |
        +--> source records
        |
        +--> evidence assessment
                 |
                 v
       IRRBBSourceCertificationReport
                 |
                 v
       READY / INCOMPLETE / BLOCKED
                 |
                 v
IRRBBSourceSnapshotAssembler
        |
        +-- READY ------> mapper executes
        |                  |
        |                  +--> canonical record or mapper failure
        |
        +-- INCOMPLETE --> SOURCE_RECORD_REJECTED
        |
        +-- BLOCKED -----> SOURCE_RECORD_REJECTED
        |
        v
IRRBBSourceSnapshot
```

The certification report is supplied to `assemble()` for each snapshot. It is deliberately not stored in the assembler constructor because evidence sufficiency may change by cutoff, workbook version, detected schema or accepted source rows.

## 3. Enforcement invariants

Phase 13 establishes the following fail-closed rules:

- `source_certification` is mandatory for every source-record assembly.
- The delegated `IRRBBCanonicalPositionMapper` executes only when `source_certification.is_ready` is true.
- `INCOMPLETE` certification cannot produce canonical positions.
- `BLOCKED` certification cannot produce canonical positions.
- Every source record rejected by certification remains visible as an `IRRBBSourceMappingFailure` with code `SOURCE_RECORD_REJECTED`.
- Certification rejections preserve the original `source_record_id` and `source_reference` unchanged.
- The rejection message records the certification profile code, version, aggregate status and unresolved blocking / not-assessed requirement identifiers.
- No missing canonical value is defaulted, imputed or fabricated to obtain `READY` behavior.
- A mapper that changes source lineage remains rejected under the existing Phase 9 invariant.

## 4. Snapshot binding

Certification is snapshot-dependent. Therefore the contract is:

```python
assembler.assemble(
    cutoff_date=cutoff,
    source_records=records,
    source_certification=certification_for_this_snapshot,
)
```

A certification from a previous cutoff is not implicitly retained by `IRRBBSourceSnapshotAssembler`.

Phase 13 does not add an automatic date-equivalence claim between `profile.effective_from`, the source cutoff and the evidence date. Those controls require explicit provenance contracts and must not be inferred by the ACL.

## 5. Treatment of curve points

The Phase 13 certification gate controls source records entering the canonical **position** mapper. Existing `IRRBBCurveSourcePoint` inputs remain independent because approved curve-source certification is a separate common-data concern.

This phase therefore does not imply that a `READY` position-source certification also certifies curves, FX conversion or Tier 1 capital.

## 6. Effect on the institutional investment master

The Phase 12 assessment remains authoritative. The institutional investment master is not promoted to production composition by Phase 13.

Known unresolved investment requirements remain unresolved, including as applicable:

- workbook-native cutoff provenance;
- canonical instrument class;
- banking-book side;
- payment structure;
- optionality classification;
- contractual next reset date for floating positions;
- contractual repricing frequency for floating positions;
- common EVE dependencies such as approved curves, FX and Tier 1 capital.

Until the relevant certification report is `READY`, source records from that candidate are rejected before its mapper can create canonical positions.

## 7. Verification

Phase 13 unit tests must prove that:

1. a `READY` certification preserves the existing Phase 9 mapping behavior;
2. mapper-level failures are still retained rather than dropped;
3. source-lineage validation still rejects a mapper that changes lineage;
4. an `INCOMPLETE` certification produces zero canonical positions and never invokes the mapper;
5. a `BLOCKED` certification produces zero canonical positions and never invokes the mapper;
6. certification-generated failures preserve record lineage and expose deterministic certification diagnostics.

## 8. Completion gate

Phase 13 is complete only when the exact pull-request head passes the full repository CI and Security workflows. No previous-head result may authorize merge after a new commit.

Completion of Phase 13 authorizes later work on physical canonical mappers only behind this enforcement boundary. It does not authorize production source composition until the applicable source-certification profile is `READY`.
