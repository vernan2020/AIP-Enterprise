# IRRBB Phase 17 — Obligations workbook schema inspection

## Purpose

Phase 17 introduces an evidence-only inspector for the institutionally designated obligations-with-entities workbook registered in Phase 16.

The governed physical source is `Auxiliar Obligaciones Entidades 2026.xlsx`. The current workstation-visible path supplied operationally is intentionally **not** embedded in executable code. Runtime/deployment configuration remains responsible for resolving `irrbb.sources.borrowing.workbook` to the appropriate local or service-account location.

This phase answers two questions only:

1. Did AIP inspect the exact governed workbook and what workbook/worksheet topology was actually observed?
2. Given an explicitly declared worksheet and header row, what exact text labels were present?

It does not decide whether the workbook is contractually sufficient for RTILB.

## Inspection sequence

```text
Phase 16 governed physical-source identity
        ↓
configured path supplied by deployment/caller
        ↓
BorrowingWorkbookSchemaInspector.discover(...)
        ↓
file validation + SHA-256 fingerprint
        ↓
worksheet names / visibility / observed topology
        ↓
explicit sheet_name + explicit header_row
        ↓
BorrowingWorkbookSchemaInspector.inspect_declared_header(...)
        ↓
exact header evidence + blank/duplicate diagnostics
        ↓
future field-level evidence assessment and certification
```

## Fail-closed controls

The inspector enforces the following controls:

- the path must exist and be a regular file;
- the source must be `.xlsx`;
- the basename must exactly match the Phase 16 governed source identity;
- unreadable/corrupt workbooks raise an explicit error;
- an empty workbook is rejected;
- worksheet selection is exact and caller-supplied; there is no fuzzy or heuristic selection;
- header-row selection is a positive, caller-supplied row number;
- the declared header row cannot exceed the last observed non-empty row;
- blank header cells remain blank evidence and are not assigned synthetic names;
- non-text header values are rejected rather than silently coerced;
- duplicate header labels are reported using a diagnostic normalization only; labels stored as evidence remain unchanged;
- source references expose source ID, basename and SHA-256 fingerprint, not a personal filesystem path.

Whitespace-only cell values are treated as observationally empty when worksheet topology is counted. This affects topology diagnostics only and does not transform contractual data.

## Why the existing investment-reader heuristic is not reused

`InstitutionalPortfolioMasterReader` has a source-specific convenience mechanism that scans candidate rows and chooses a likely header based on known investment aliases. That behavior is appropriate for its established investment ingestion contract, but it must not be generalized to a new liability source whose schema has not yet been evidenced.

For obligations, Phase 17 requires the worksheet and header row to be declared explicitly. This prevents a visually similar sheet or header from being accepted by score and subsequently treated as contractual evidence.

## Evidence model

### `BorrowingWorkbookDiscovery`

Captures:

- governed source ID;
- safe source reference;
- basename;
- SHA-256 file fingerprint;
- all worksheets discovered.

### `BorrowingWorkbookSheetTopology`

For every worksheet captures:

- exact sheet name;
- visibility state;
- workbook-reported maximum row/column;
- observed non-empty row count;
- observed non-empty cell count;
- last observed non-empty row;
- last observed non-empty column.

The distinction between workbook-reported dimensions and observed values is deliberate: spreadsheet dimensions may include formatting or historical artifacts and are not, by themselves, proof of populated contractual records.

### `BorrowingWorkbookHeaderInspection`

For the explicitly declared header row captures:

- exact column indexes and Excel letters;
- exact text labels;
- blank column indexes;
- duplicate labels.

No aliases or canonical RTILB field names are assigned in this phase.

## Certification status

Phase 17 does **not** create or alter an `IRRBBSourceCertificationReport` for obligations. The source remains schema-`NOT_ASSESSED` until the real institutional workbook is inspected and its columns are mapped against a versioned LIABILITY requirement profile with source evidence.

In particular, Phase 17 does not assume availability of:

- operation/contract identifier;
- principal or carrying amount;
- currency;
- contractual rate;
- fixed/floating rate type;
- maturity date;
- next repricing date;
- repricing frequency;
- payment frequency;
- contractual cash-flow schedule;
- embedded options or behavioral assumptions.

Any of these may exist in the real workbook, but existence must be established from inspection evidence before it can be certified.

## Explicit exclusions

Phase 17 does not:

- hardcode `C:\\Users\\ahidalgo\\...` or any other workstation path;
- read ICL as a contractual liability source;
- fall back to SQL `VISTA_1514_1515_1516`;
- infer columns from a similarly named field;
- normalize data rows;
- manufacture missing fields;
- map a workbook row into `BankingBookPosition`;
- create contractual schedules;
- mark the obligations source `READY`;
- modify GAP, EVE, NII or scenario calculations;
- wire the workbook into production runtime composition.

## Next gate

After this inspector is executed against the real institutional workbook, the resulting sheet/header evidence must be reviewed. A subsequent phase may then define a versioned obligations requirement profile and source-evidence assessor. Only evidence-backed native fields or explicitly documented derivations may advance certification; unresolved mandatory variables must remain `NOT_ASSESSED` or blocking as appropriate.
