# IRRBB Phase 4A — Calculation orchestration

## Objective

This phase composes the source-agnostic IRRBB domain into an auditable calculation
sequence without selecting SQL, XML, OneDrive, Excel, PostgreSQL or any physical
market-data source.

It remains separate from the SUGEF 2023 repricing-GAP path.

## Scenario position cash flows

The orchestration boundary is `ScenarioPositionCashFlowProvider`:

```text
BankingBookPosition + Scenario + ValuationDate
                         |
                         v
             final scenario cash flows
```

This interface intentionally owns instrument-specific ordering of contractual schedule,
repricing and behavior. The top-level EVE orchestrator therefore does not assume that
all optional products can apply behavioral and repricing transformations in the same
order.

`StandardScenarioPositionCashFlowProvider` currently implements only calculation paths
that are sufficiently specified:

1. fixed-rate positions without material optionality: contractual flows are unchanged;
2. floating-rate positions without material optionality: BASE uses the transparent base
   projection and stressed scenarios require `ScenarioCashFlowProjector`;
3. non-maturity deposits: the approved NMD behavioral model supplies scenario cash flows.

The provider rejects loan prepayment, term-deposit early withdrawal and other material
optionality until an integrated instrument-specific strategy is approved. This is a
calculation-safety control, not a missing feature silently approximated by the engine.

## BASE + six scenario evaluation

`IRRBBScenarioEvaluationService` executes:

```text
calculation-ready positions
        |
        +--> BASE cash flows --> discount --> EVE base
        |
        +--> PARALLEL_UP   --> discount --> EVE S1
        +--> PARALLEL_DOWN --> discount --> EVE S2
        +--> STEEPENER     --> discount --> EVE S3
        +--> FLATTENER     --> discount --> EVE S4
        +--> SHORT_UP      --> discount --> EVE S5
        +--> SHORT_DOWN    --> discount --> EVE S6
                                      |
                                      v
                          DeltaEVEExposureService
                                      |
                                      v
                       worst loss / Tier 1 capital
```

The six scenarios remain the default target set. The service validates that the stress
set is non-empty, contains no BASE scenario and contains no duplicates.

For every position/scenario, the scenario cash-flow provider must return at least one
cash flow in the position's own currency and with the same position identifier. Empty or
misrouted flows fail explicitly rather than disappearing from EVE.

## Economic value

Each scenario is passed to the already-certified `EconomicValueService`:

```text
EVE = PV(assets) - PV(liabilities) + PV(off-balance net)
```

Discount factors and FX conversion remain injected ports. This orchestration phase does
not define curve interpolation, discount compounding, market source or FX source.

The resulting `IRRBBScenarioEvaluationResult` stores:

- methodology/version metadata;
- valuation date;
- reporting currency;
- number of included positions;
- BASE EVE result with per-flow valuation trace;
- stressed EVE results;
- Delta EVE / worst-loss / Tier-1 exposure result.

## Quality gate

The orchestrator assumes that the input set has already passed the applicable
calculation-readiness assessment. It nevertheless applies defensive controls for:

- empty position set;
- duplicate position IDs;
- missing scenario cash flows;
- cash flows attributed to another position;
- cash-flow currency inconsistent with the normalized position;
- malformed stress scenario sets.

The future application layer will combine this with `IRRBBPositionDataQualityService`
and source-sufficiency diagnostics before calling the calculation engine.

## Separation from SUGEF GAP

The SUGEF GAP workbook continues to use:

```text
SugefGapRowClassifierService
SugefStandardGapService
IRRBBTimeBucketService
```

It does not feed its banded notional amounts into EVE. Both views share normalized
source data but preserve distinct calculation semantics.

## Next stage

The next safe stage is the application/read-model layer for the future UI:

- calculation readiness summary;
- EVE BASE and six scenarios;
- Delta EVE and Tier-1 ratio;
- 19-band SUGEF GAP matrix;
- per-position/per-flow drill-down;
- data-quality and mapping-pending panels;
- methodology/version disclosure.

No graphical widget should perform financial calculations; the UI consumes only these
application/domain results.
