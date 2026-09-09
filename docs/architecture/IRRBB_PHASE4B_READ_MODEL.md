# IRRBB Phase 4B — Read model and presenter

## Objective

Phase 4B introduces the passive presentation boundary for the future **Riesgo de Tasa /
RTILB** workspace. It does not add PySide6 widgets and does not change any financial
methodology.

The presentation flow is:

```text
certified domain/application results
              |
              v
       RateRiskPresenter
              |
              v
       RateRiskReadModel
              |
              v
       future passive UI
```

No discounting, repricing, scenario construction, behavioral modeling, FX conversion,
SUGEF GAP aggregation or curve interpolation is performed by the presenter.

## Read-model sections

The immutable `RateRiskReadModel` contains:

- methodology/version/cutoff disclosure;
- calculation-readiness summary;
- KPI cards for base VEP, worst Delta VEP loss, Delta VEP/CN1, CN1 and position count;
- BASE + six stress scenario rows;
- SUGEF GAP bucket totals supplied by the calculation path;
- optional already-aggregated SUGEF report-line x bucket matrix cells;
- per-scenario discounted cash-flow drill-down;
- position-level data-quality summary;
- issue-level data-quality details;
- SUGEF row-classification/mapping status;
- already-resolved base/shocked curve points;
- explicit warnings when quality, matrix or curve inputs have not yet been supplied.

## Scenario presentation

The presenter reads `IRRBBScenarioEvaluationResult` directly. It does not recompute
Delta VEP.

It verifies that the stressed VEP scenario set and the `DeltaEVEResult.assessments`
scenario set have identical coverage before exposing them to the view.

The displayed scenario set is:

1. Base
2. Paralelo +
3. Paralelo -
4. Empinamiento
5. Aplanamiento
6. Corto +
7. Corto -

The worst scenario flag comes from `DeltaEVEResult.worst_scenario`; it is not selected
again in the presentation layer.

## SUGEF GAP

Two presentation levels are intentionally distinguished:

### Bucket totals

`SugefGapBucketTotal` values can be exposed directly as ordered band totals.

### Full supervisory matrix

`RateRiskGapMatrixCellInput` accepts amounts that have **already** been aggregated by:

```text
SUGEF report line x temporal bucket
```

The presenter only labels and orders those values. It does not derive a report-line
matrix from portfolio positions.

This preserves the separation between:

- row classification;
- SUGEF GAP exposure generation;
- aggregation;
- presentation.

Until the application layer supplies all approved matrix cells, the read model reports
that the matrix has not been supplied rather than filling missing values with invented
zeros.

## Curves

`RateRiskCurvePointInput` is a transport structure for an already-resolved curve point.
It contains:

- curve identifier;
- as-of date;
- currency;
- scenario;
- tenor;
- rate;
- source reference.

The presentation layer does **not**:

- interpolate;
- extrapolate;
- apply shocks;
- select a curve;
- calculate discount factors.

Those responsibilities remain behind the approved market/methodology ports.

## Drill-down

Every `DiscountedCashFlow` produced by the VEP engine is exposed with:

- scenario;
- position;
- balance-sheet side;
- direction;
- flow type/status;
- payment date;
- risk date;
- amount/currency;
- discount factor;
- FX rate;
- present value;
- signed VEP contribution;
- source reference;
- projection basis.

This provides the audit trail needed to explain any scenario result without recalculating
inside the GUI.

## Data quality and mapping

`IRRBBPositionAssessment` is transformed into:

- one position-level readiness row; and
- zero or more issue-detail rows.

`SugefGapRowClassification` is exposed separately, including `MAPPING_PENDING` and
`INCOMPLETE` states. Pending account/family mappings therefore remain visible instead of
being silently assigned.

## Safety boundary

The future PySide6 view is allowed to:

- filter;
- sort;
- select;
- format;
- chart values already present in the read model.

It is not allowed to:

- calculate VEP or Delta VEP;
- shock rates;
- rebuild cash flows;
- infer missing dates/rates;
- aggregate SUGEF exposures;
- generate behavioral assumptions;
- create missing supervisory matrix values.

## Next stage

After this phase is certified, the next safe step is **Phase 4C — application query /
composition boundary**:

1. obtain calculation-ready positions;
2. execute the scenario evaluation;
3. obtain SUGEF GAP outputs;
4. obtain quality and mapping diagnostics;
5. obtain curve snapshots;
6. call `RateRiskPresenter`;
7. hand one immutable read model to the future workspace.

Physical source adapters remain outside that boundary.
