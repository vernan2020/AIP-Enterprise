# IRRBB Phase 6 — Analysis orchestration

## Objective

Phase 6 composes the source-readiness boundary from Phase 5 with the certified IRRBB domain services. It produces an application result suitable for later presentation without introducing any dependency on PySide6 or on a physical source technology.

## Calculation perimeter

Only positions classified `READY` by `LoadIRRBBSourceSnapshot` are passed to the economic-value engine. If no position is ready, the result is explicitly `BLOCKED`; Tier 1 capital and scenario valuation are not requested.

The economic-value path uses:

- `IRRBBScenarioEvaluationService` for BASE plus the required stress scenarios;
- `TierOneCapitalProvider` for the RTILB exposure denominator;
- the existing scenario cash-flow, discount-factor and exchange-rate ports already composed by the domain service.

No source field is interpreted in this use case and no missing financial assumption is imputed.

## SUGEF GAP path

SUGEF GAP remains separate from the EVE/Delta EVE calculation.

For each calculation-ready position:

1. `SugefGapRowClassifierService` resolves the supervisory row;
2. only a `MAPPED` position with an explicit normalized GAP schedule enters GAP aggregation;
3. a missing schedule creates `SCHEDULE_MISSING` and is not treated as zero exposure;
4. an invalid schedule creates `SCHEDULE_INVALID` and does not invalidate an otherwise valid EVE result;
5. an unmapped row creates `ROW_NOT_MAPPED`.

GAP results are aggregated independently by native currency. CRC and USD are never netted or converted inside the SUGEF GAP result. Each currency result contains bucket totals, row/bucket matrix cells and the exact included position identifiers.

## Application statuses

- `NO_DATA`: the source snapshot is empty.
- `BLOCKED`: data exists but no position is calculation-ready.
- `CALCULATED`: EVE/Delta EVE is calculated and all ready positions have complete SUGEF GAP coverage.
- `CALCULATED_WITH_DATA_GAPS`: EVE/Delta EVE is calculated, but source readiness or SUGEF GAP coverage is partial.

## Boundary to the UI

`IRRBBAnalysisResult` is an application contract. It does not import UI DTOs. A subsequent presentation adapter may transform:

- scenario evaluation into KPI/scenario rows;
- native-currency GAP results into UI matrix rows;
- Phase 5 data-quality assessments into readiness and issue tables;
- source curve points into passive curve rows.

The UI remains a consumer and must not calculate VEP, Delta VEP, GAP, discount factors, FX conversion or behavioral assumptions.
