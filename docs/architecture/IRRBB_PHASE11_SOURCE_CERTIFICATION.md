# IRRBB / RTILB — Phase 11 Source Sufficiency Certification

## 1. Purpose

Phase 11 converts the source-sufficiency gate defined in Phase 9 into an auditable application contract.

This phase does **not** select or certify a real SQL Server, XML, Excel, OneDrive, PostgreSQL, API, or other physical source. It provides the deterministic mechanism that a future candidate must pass before it can be composed into the production IRRBB runtime.

The certification boundary remains expressed exclusively in canonical RTILB terminology.

## 2. Flow

```text
Versioned canonical RTILB requirement profile
                    |
                    v
Evidence-backed requirement assessments
                    |
                    v
IRRBBSourceCertificationService
                    |
          +---------+----------+
          |                    |
          v                    v
Requirement-level trace   Aggregate status
                               |
                    +----------+----------+
                    |          |          |
                    v          v          v
                  READY    INCOMPLETE   BLOCKED
```

The certification service does not read a source directly. A future physical adapter or source-assessment workflow supplies the evidence and classifications.

## 3. Canonical availability statuses

Each requirement must be classified with one of the statuses approved in Phase 9:

- `NATIVE_AVAILABLE`
- `DERIVABLE_WITH_DOCUMENTED_RULE`
- `AVAILABLE_FROM_SUPPLEMENTARY_SOURCE`
- `MISSING_BLOCKING_GAP`
- `MISSING_BLOCKING_EVE`
- `NOT_APPLICABLE`
- `NOT_ASSESSED`

No unassessed requirement is silently treated as available.

## 4. Evidence invariants

A status that asserts data availability must be auditable.

### Native availability

`NATIVE_AVAILABLE` requires:

- the source reference that natively contains the canonical variable;
- an evidence reference proving the assessed availability.

### Derivable availability

`DERIVABLE_WITH_DOCUMENTED_RULE` requires:

- the source reference containing the required source inputs;
- a reference to the documented, versioned derivation rule;
- an evidence reference covering the assessment/derivation.

The rule reference is the governance anchor for source fields, effective version and test coverage. The certification contract does not embed physical field names.

### Supplementary-source availability

`AVAILABLE_FROM_SUPPLEMENTARY_SOURCE` requires:

- the supplementary source reference;
- an evidence reference proving the required canonical variable is available from that source.

### Not applicable

`NOT_APPLICABLE` requires an explicit rationale in `notes`. This prevents `NOT_APPLICABLE` from becoming an undocumented bypass of the certification gate.

## 5. Requirement profile invariants

A requirement profile is:

- identified by code and version;
- effective-dated;
- linked to a source/reference document;
- non-empty;
- composed of unique requirement IDs;
- expressed in canonical RTILB variables and perimeters only.

A zero-requirement profile is invalid because it could otherwise produce a false-positive `READY` certification.

## 6. Aggregate certification logic

The service normalizes assessments into the exact order of the requirement profile.

If a required assessment is omitted, the service materializes it as `NOT_ASSESSED` rather than assuming availability.

Aggregate status is deterministic:

1. `BLOCKED` if any requirement is `MISSING_BLOCKING_GAP` or `MISSING_BLOCKING_EVE`;
2. otherwise `INCOMPLETE` if one or more requirements remain `NOT_ASSESSED`;
3. otherwise `READY`.

Blocking status has precedence over incomplete status so a known blocking gap cannot be diluted by other unassessed items.

The report retains both:

- `blocking_requirement_ids`;
- `not_assessed_requirement_ids`.

## 7. What READY means

`READY` means only that the candidate assessment is complete against the supplied **versioned canonical requirement profile** and contains the required trace/evidence metadata.

It does not mean:

- the physical source has already been approved by Coopealianza;
- the source data are correct for a specific cutoff;
- all source records will map successfully at runtime;
- the resulting banking-book positions are financially complete;
- the EVE/GAP calculation itself is valid.

Those concerns remain separated:

```text
Source certification
        |
        v
Physical adapter / ACL mapping
        |
        v
IRRBBSourceSnapshot
        |
        v
Runtime mapping diagnostics
        |
        v
IRRBBPositionDataQualityService
        |
        v
Calculation orchestration
```

This separation prevents source metadata governance from replacing record-level data-quality and financial-readiness controls.

## 8. Phase 11 completion gate

Phase 11 is complete when:

1. source certification contracts are exported from the IRRBB application package;
2. empty requirement profiles are rejected;
3. availability assertions cannot be created without the required trace/evidence references;
4. omitted requirements normalize to `NOT_ASSESSED`;
5. blocking and incomplete statuses are deterministic and separately traceable;
6. duplicate and unknown requirement IDs are rejected;
7. unit tests cover the certification invariants;
8. CI and Security are green;
9. no physical source schema, field name or storage technology enters domain/application contracts.

## 9. Next gate

Only after Phase 11 is certified should AIP assess an actual physical source candidate against a versioned requirement profile.

That future assessment must produce concrete evidence for each canonical RTILB variable and must not label the source production-ready while any blocking or unassessed requirement remains.
