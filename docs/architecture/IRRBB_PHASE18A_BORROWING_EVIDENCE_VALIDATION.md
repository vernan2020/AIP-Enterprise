# IRRBB Phase 18A — Transferred obligations evidence validation

## Purpose

Phase 18A validates the JSON evidence emitted by the Phase 18 local obligations-workbook diagnostic before that evidence can be used to design a LIABILITY source requirement profile or evidence assessor.

This supporting slice exists because Phase 19 must be grounded in the actual institutional workbook report. The report may be transferred from the workstation that can access the governed workbook, but transfer itself must not make an unverified JSON document authoritative.

Phase 18A therefore answers one question only:

> Is this document an internally consistent Phase 18 report for the exact governed obligations workbook snapshot?

It does **not** answer whether any workbook column satisfies a canonical RTILB requirement.

## Validation boundary

```text
Phase 18 local CLI
        ↓
JSON discovery/header report
        ↓
BorrowingInspectionEvidenceValidator
        ↓
strict report type/version validation
        ↓
governed source identity validation
        ↓
SHA-256 + source_reference validation
        ↓
topology/header diagnostic recomputation
        ↓
discovery/header same-snapshot binding
        ↓
validated evidence bundle
        ↓
manual review
        ↓
Phase 19 requirement profile/evidence assessor (only after real evidence exists)
```

## Governed identity

The validator imports the existing `BORROWING_WORKBOOK_SOURCE` descriptor and requires the exact source identity already established in Phase 16:

- source ID: `coopealianza.liability.excel.obligaciones_entidades`;
- file name: `Auxiliar Obligaciones Entidades 2026.xlsx`.

The identity is not redefined locally.

`source_reference` must be exactly reconstructable as:

```text
<source_id>:<source_file_name>#sha256=<64-lowercase-hex-digest>
```

A different source ID, filename, malformed digest or mismatched source reference is rejected.

## Exact-version contract

Only the current Phase 18 report version is accepted. Unknown top-level or nested fields are rejected rather than ignored.

This strictness is deliberate. If the diagnostic report contract changes, its version and validator must change together. A future report cannot silently acquire additional fields such as `rows`, `balances`, aliases or canonical mappings and still be treated as equivalent evidence.

## Discovery validation

For `IRRBB_BORROWING_WORKBOOK_DISCOVERY`, Phase 18A requires:

- exact report shape;
- at least one worksheet;
- unique worksheet names;
- recognized worksheet visibility states;
- non-negative integer topology values, excluding booleans;
- observed rows/columns within workbook-reported bounds;
- observed cell counts consistent with observed row counts and worksheet capacity;
- zero observed topology to remain internally zero rather than carrying contradictory bounds.

The validator does not infer which worksheet is the contractual data sheet.

## Header validation

For `IRRBB_BORROWING_WORKBOOK_HEADER`, Phase 18A requires:

- exact report shape;
- a nonblank explicitly selected worksheet name;
- a positive 1-based header row;
- at least one physical header cell and at least one text label;
- contiguous 1-based physical column indexes;
- an Excel column letter that exactly matches each index;
- each label to be either `null` or nonblank text;
- `blank_column_indexes` to equal the blanks recomputed from the cell evidence;
- `duplicate_labels` to equal the duplicates recomputed using the same diagnostic normalization as Phase 17.

Exact labels remain unchanged. The duplicate computation is diagnostic only and does not normalize the evidence stored for later review.

## Same-snapshot binding

A discovery report and a header report can form `BorrowingInspectionEvidenceBundle` only when they have identical:

- report version;
- source ID;
- source reference;
- source filename;
- SHA-256 fingerprint.

The selected header worksheet must also exist in discovery evidence, the selected row must lie within the observed worksheet topology, and the physical header-cell span must equal the observed last non-empty column captured for that sheet.

This prevents a header report from one workbook revision from being paired with discovery evidence from another revision.

## Fail-closed invariants

1. JSON root must be an object and report type must be recognized.
2. Unknown report versions are rejected.
3. Unknown fields are rejected rather than ignored.
4. The governed Phase 16 source identity is authoritative.
5. SHA-256 is syntactically validated and bound into the safe source reference.
6. Workbook topology cannot contradict itself.
7. Header coordinates and diagnostics must be independently recomputable.
8. Discovery and header evidence must refer to the same physical snapshot before bundling.
9. No contractual row, balance or schedule is accepted as part of the inspection-evidence contract.
10. Valid evidence does not imply source certification readiness.

## Explicit exclusions

Phase 18A does not:

- inspect the workbook itself;
- introduce a second Excel reader;
- choose a worksheet or header row;
- infer aliases from header names;
- assign canonical RTILB fields;
- define a LIABILITY requirement profile;
- mark any requirement `NATIVE_AVAILABLE`, `DERIVABLE_WITH_DOCUMENTED_RULE` or `READY`;
- map any row to `BankingBookPosition`;
- construct contractual schedules;
- use ICL or `VISTA_1514_1515_1516` as a fallback;
- modify GAP, EVE, NII or scenario calculations;
- wire the obligations workbook into production runtime composition.

## Phase 19 gate

Phase 19 remains blocked until the real institutional workbook is inspected with Phase 18 and the resulting discovery/header JSON is available for review.

Once a real report is available, it must first pass Phase 18A validation. Only then may a later slice define the versioned LIABILITY requirement profile and evidence assessor, and only fields actually present in the validated header evidence may be proposed as native source candidates.
