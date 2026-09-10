# IRRBB Phase 18 — Safe local obligations inspection CLI

## Purpose

Phase 18 makes the Phase 17 obligations-workbook inspector executable on the institutional workstation that has access to the governed workbook, without wiring that workbook into the AIP production runtime and without exporting contractual data rows.

The command is a thin diagnostic shell over `BorrowingWorkbookSchemaInspector`. It does not add a second source-reading implementation.

## Execution model

The module is invoked directly with Python:

```text
python -m aip.product.configured.irrbb.borrowing_workbook_inspection_cli --path "<configured-obligations-workbook>"
```

Discovery mode emits a JSON report containing the governed source identity, SHA-256 fingerprint and worksheet topology.

After reviewing the exact worksheet names, a second explicit invocation may inspect one declared header row:

```text
python -m aip.product.configured.irrbb.borrowing_workbook_inspection_cli --path "<configured-obligations-workbook>" --sheet "<exact-sheet-name>" --header-row <N>
```

`--sheet` and `--header-row` must be supplied together. The command never guesses either value.

Standard output contains only JSON on success. It can therefore be redirected to a file when evidence needs to be reviewed or transferred:

```text
python -m aip.product.configured.irrbb.borrowing_workbook_inspection_cli --path "<configured-obligations-workbook>" > borrowing-discovery.json
```

The actual workstation-specific OneDrive path is intentionally absent from source code and documentation examples. Deployment or the operator supplies it at execution time.

## Discovery report

`IRRBB_BORROWING_WORKBOOK_DISCOVERY` contains:

- report version;
- governed source ID;
- safe source reference;
- governed workbook basename;
- SHA-256 fingerprint;
- every observed worksheet with its visibility and topology counts.

The report does **not** contain the input parent path, workbook data rows, contractual balances or certification status.

## Header report

`IRRBB_BORROWING_WORKBOOK_HEADER` contains the same safe source identity plus:

- exact selected worksheet name;
- exact 1-based header row;
- column indexes and Excel letters;
- exact text labels observed by Phase 17;
- blank-column indexes;
- duplicate-label diagnostics.

No data row below the selected header is serialized by the CLI.

## Return codes

- `0`: inspection completed and one JSON report was emitted;
- `1`: the governed workbook could not be inspected under the Phase 17 fail-closed rules;
- `2`: command-line usage was invalid.

Inspection failures do not emit partial JSON. Generic filesystem errors are intentionally sanitized so an operating-system exception cannot disclose a workstation parent path in a report transcript.

## Architecture boundary

```text
local operator / diagnostic shell
        ↓
borrowing_workbook_inspection_cli
        ↓
BorrowingWorkbookSchemaInspector  (Phase 17)
        ↓
safe discovery/header JSON evidence
        ↓
manual evidence review
        ↓
future LIABILITY requirement profile + evidence assessor
```

The CLI does not belong to domain logic and does not become an `IRRBBDataGateway`. It imports the already governed configured-source inspector and only serializes its evidence contracts.

## Fail-closed invariants

1. The Phase 17 exact source-name, `.xlsx`, readability and SHA-256 consistency controls remain authoritative.
2. The CLI does not auto-select a worksheet or header row.
3. Header mode is unavailable unless both explicit parameters are present.
4. A command failure emits no partial JSON document.
5. Parent filesystem paths are not part of successful report payloads.
6. Contract data rows are never serialized by either report type.
7. No field is mapped to canonical RTILB terminology in this phase.
8. No source requirement is promoted to `READY`, `NATIVE_AVAILABLE` or `DERIVABLE_WITH_DOCUMENTED_RULE` by running the command.

## Explicit exclusions

Phase 18 does not:

- add or modify the AIP main executable entry point;
- hardcode a workstation path;
- connect to OneDrive, Power BI, Fabric or OneLake;
- read ICL as a contractual liability source;
- fall back to `VISTA_1514_1515_1516`;
- export borrowing rows or balances;
- infer aliases or canonical fields;
- build `BankingBookPosition` objects;
- create cash-flow schedules;
- certify the obligations source;
- modify GAP, EVE, NII or scenario calculations;
- wire obligations into production runtime composition.

## Next gate

The intended operational sequence is:

1. run discovery mode against the real governed workbook;
2. review the returned exact worksheet names and topology;
3. explicitly select the institutional data worksheet and its header row;
4. run header mode;
5. review the resulting JSON evidence;
6. only then define the versioned LIABILITY source-requirement profile and evidence assessor.

Phase 19 must be grounded in the actual report. A field that does not appear in the evidenced workbook schema must not be silently manufactured or inferred from another source.
