# IRRBB Phase 15 — Institutional Investment Master Batch Bridge

## Purpose

Phase 15 connects the already approved investment-source components into one auditable, still-passive batch path:

1. `InstitutionalPortfolioMasterReadResult` from the institutional reader;
2. Phase 12 `InvestmentMasterSourceEvidenceAssessor`;
3. source-record envelopes with file/sheet/row lineage;
4. Phase 13 mandatory certification gate in `IRRBBSourceSnapshotAssembler`; and
5. the mapper contract introduced in Phase 14.

The bridge does **not** improve, override, or reinterpret source certification. Its purpose is to prove that the physical investment-master path remains fail-closed when the evidence report is not `READY`.

## Components

### `InstitutionalInvestmentMasterEnvelopeFactory`

The factory converts each accepted normalized master row into an `IRRBBSourceRecordEnvelope[InvestmentMasterSourcePayload]`.

Each envelope preserves:

- source file basename;
- selected sheet;
- source row number;
- the normalized reader position; and
- the reader's canonical-to-native `detected_column_mapping`.

`source_record_id` is adapter lineage only. It is intentionally distinct from canonical `position_id`. The factory therefore may use file/sheet/row identity for source auditing while Phase 14 continues to require contract + ISIN or contract + series for canonical cross-cutoff position identity.

Source file basenames are normalized independently of the host operating system. This is necessary because AIP production paths are Windows-oriented while CI executes on Linux. Full local directory paths are not propagated into the bridge's source references.

Missing source file, missing selected sheet, non-positive/non-integer source row numbers, and duplicate file/sheet/row lineage are rejected explicitly.

### `InstitutionalInvestmentMasterBatchBridge`

The bridge:

1. prepares source envelopes;
2. runs `InvestmentMasterSourceEvidenceAssessor.assess()` without modification;
3. passes that exact certification report to `IRRBBSourceSnapshotAssembler`; and
4. returns both certification and snapshot in `InvestmentMasterBatchBridgeResult`.

There is no alternate path around the Phase 13 gate.

## Current expected behavior

For the currently evidenced institutional investment master, a fixed-rate batch can satisfy several source requirements but Phase 12 still leaves at least the following unresolved unless separately certified:

- `INV-CUTOFF-DATE`;
- `INV-INSTRUMENT-CLASS`;
- `INV-SIDE`;
- `INV-PAYMENT-STRUCTURE`; and
- `INV-OPTIONALITY`.

Accordingly, the current fixed-rate candidate remains `INCOMPLETE`. If blocking source gaps exist — for example a floating-rate position without certified contractual reset terms — the certification is `BLOCKED`.

In either case, the Phase 13 assembler rejects every prepared source record with auditable `SOURCE_RECORD_REJECTED` failures and **does not invoke the Phase 14 mapper**.

This is intentional. Phase 15 is an orchestration and safety proof, not source activation.

## Cutoff semantics

`cutoff_date` supplied to the bridge is the requested snapshot context. It is not promoted to source evidence.

The reader can receive a valuation-date override and the configured portfolio discovery flow can select prior source files when explicitly allowed. Therefore equality between a requested cutoff and `result.valuation_date` is not sufficient evidence that the workbook itself represents that cutoff.

`INV-CUTOFF-DATE` remains governed by the source-certification layer until an explicit source-selection/cutoff provenance rule is approved and evidenced.

## Reader rejections and warnings

`InvestmentMasterBatchBridgeResult` retains:

- `reader_rejected_row_count`; and
- `source_warnings`.

Those fields make upstream parsing loss visible to callers. However, the current reader result does not retain complete per-row payload/lineage for every rejected row; therefore Phase 15 cannot manufacture canonical mapping failures for data that no longer exists at its boundary.

This limitation must remain an activation gate. Before production RTILB use, either:

- reader rejection lineage must be made complete and auditable; or
- an approved completeness policy must demonstrate that excluded rows are outside the RTILB perimeter.

No rejected-row count may be silently treated as zero or ignored when production activation is designed.

## Relationship to Phase 14 policy

Phase 15 accepts any mapper implementing `IRRBBCanonicalPositionMapper[InvestmentMasterSourcePayload]`, which keeps the orchestration decoupled from a concrete policy implementation and makes the certification gate independently testable.

A production `InstitutionalInvestmentMasterCanonicalMapper` still requires an approved, effective-dated `InvestmentMasterCanonicalMappingPolicy`. Phase 15 does not create such a policy and does not declare any Coopealianza product/classification combination approved.

## Runtime status

The bridge is exported from `aip.product.configured.irrbb` for composition testing, but it is **not** wired into `ConfiguredIRRBBComposition` or the application runtime.

No current dashboard, portfolio, liquidity, price-risk, EVE, GAP, NII, DV01, VaR, HQLA, MIL, or econometric calculation path is changed by Phase 15.

## Remaining activation gates

Investment-source activation still requires explicit evidence and governance for, at minimum:

1. cutoff/source-selection provenance;
2. a complete and approved product/classification mapping policy;
3. instrument class, side, payment structure, optionality and principal semantics;
4. contractual reset date/frequency for every floating-rate investment position;
5. source completeness/rejected-row treatment;
6. policy applicability to the requested cutoff;
7. parity tests against an approved institutional benchmark; and
8. full CI and security validation of the eventual runtime composition.

Credit and liability sources remain outside Phase 15 and remain `NOT_ASSESSED` until granular contractual source evidence is demonstrated. The aggregate ICL source is not a substitute for contractual liability records, and the SQL Server view `VISTA_1514_1515_1516` must not be treated as sufficient without field-level proof.
