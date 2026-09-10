# IRRBB / RTILB Domain Blueprint

## 1. Purpose

This document defines the source-independent domain core for **Interest Rate Risk in the Banking Book (IRRBB / RTILB)** in AIP Enterprise.

The current implementation covers the **economic value perspective (VEP / EVE)** domain core plus instrument/schedule readiness. Data connectors, database technology and PySide6 views remain outside this boundary. A later NII/margin engine will share the same canonical position, repricing and behavioral assumptions without mixing its calculation rules with EVE.

## 2. Methodological governance

The January 2024 SUGEF sector presentation is treated as a **proposed / prospective methodology source**, not as an automatically effective regulation. Its VEP structure, six stress scenario families, 19 time bands, Tier 1 exposure concept and proposed buffer schedule therefore enter AIP through versioned methodology/parameter objects.

No proposed shock, threshold or capital buffer is hardcoded in calculation services.

AIP must be able to host, concurrently:

1. current effective SUGEF methodology;
2. SUGEF prospective/proposed IRRBB methodology;
3. internal Basel-aligned ALM methodology.

Every result must identify the methodology version and source used.

## 3. Architecture boundary

```text
OneDrive / SQL / XML / Excel / PostgreSQL / API
                       |
                       v
             Source-specific adapters
                       |
                       v
              BankingBookPosition
                       |
          +------------+-------------+
          |                          |
          v                          v
Investment strategy       Normalized contractual schedule
(reuses portfolio engine)  (credit/deposit/borrowing/OFB)
          |                          |
          +------------+-------------+
                       v
                 IRRBBCashFlow
                       |
       +---------------+----------------+
       |                                |
       v                                v
Scenario repricing projector       Behavioral model
       |                                |
       +---------------+----------------+
                       v
              19 time-bucket trace
                       |
                       v
       Base / shocked curve providers
                       |
                       v
                Economic Value
                       |
                       v
             Base + 6 stresses
                       |
                       v
              Delta EVE / VEP
                       |
                       v
              Maximum EVE fall
                       |
                       v
              Exposure / Tier 1
                       |
                       v
        Versioned capital-buffer schedule
```

The domain layer never opens files, queries SQL, reads OneDrive or knows about widgets.

## 4. Canonical position contract

`BankingBookPosition` is the anti-corruption boundary between external source schemas and IRRBB. It contains, at minimum:

- stable position identifier;
- product type and balance-sheet side;
- canonical instrument class;
- payment structure;
- currency;
- principal and optional carrying amount;
- fixed/floating classification;
- contractual rate, reference rate and spread when available;
- maturity;
- next repricing date and repricing frequency;
- payment frequency;
- last/next payment dates when available;
- cap/floor when available;
- optionality classification;
- source trace/reference.

Missing mandatory information is not silently imputed.

The canonical instrument classes currently distinguish investments, credit, term deposits, borrowings, non-maturity deposits, off-balance positions and other/unclassified records. Source product codes remain outside the IRRBB strategy selection logic.

## 5. Cash-flow ownership

Instrument-specific cash-flow builders own contractual schedule generation. The generic IRRBB engine consumes canonical `IRRBBCashFlow` objects and does not recreate instrument calendars.

For investments, `InvestmentContractualCashFlowBuilder` **reuses `PortfolioContractualCashFlowService`**, which is already the canonical AIP portfolio coupon/principal schedule. A second investment coupon calendar is prohibited.

For credit, term deposits, borrowings and off-balance positions, the safe current strategy is `ExplicitScheduleCashFlowBuilder`. It consumes a `ContractualCashFlowScheduleProvider` containing normalized, auditable payment records. AIP does not invent an amortization table or day-count convention merely because a balance, rate and final maturity are present.

A future source adapter may either supply a native contractual schedule or derive one from sufficiently complete contractual terms. In both cases the result crossing into IRRBB is the same typed `ContractualCashFlowRecord` contract.

`IRRBBCashFlow` distinguishes:

- `cashflow_date`: contractual/behavioral payment date;
- `risk_date`: date selected by the repricing strategy for risk traceability;
- `amount_status`: contractual, source-provided, current-rate projection, scenario projection or behavioral;
- `projection_basis`: optional trace of the projection source/strategy.

`risk_date` is not, by itself, a repricing-GAP notional. A later GAP engine must apply the corresponding instrument strategy rather than summing future payment amounts indiscriminately at the reset date.

## 6. Nineteen temporal buckets

The target standardized structure is represented explicitly:

1. 1 day;
2. >1 day to 1 month;
3. >1 to 3 months;
4. >3 to 6 months;
5. >6 to 9 months;
6. >9 months to 1 year;
7. >1 to 1.5 years;
8. >1.5 to 2 years;
9. >2 to 3 years;
10. >3 to 4 years;
11. >4 to 5 years;
12. >5 to 6 years;
13. >6 to 7 years;
14. >7 to 8 years;
15. >8 to 9 years;
16. >9 to 10 years;
17. >10 to 15 years;
18. >15 to 20 years;
19. >20 years.

`IRRBBTimeBucketService` uses true calendar-month boundaries, not fixed 30-day approximations.

## 7. Scenarios

The domain recognizes:

- BASE;
- PARALLEL_UP;
- PARALLEL_DOWN;
- STEEPENER;
- FLATTENER;
- SHORT_UP;
- SHORT_DOWN.

`ScenarioShockCalibration` stores versioned parallel/short/long shock magnitudes in basis points, but it does **not** assume the mathematical interpolation used to build non-parallel shocked curves.

The exact tenor transformation belongs to a `ScenarioCurveShocker` implementation tied to an approved regulatory methodology version. This prevents AIP from inventing a steepener/flattener formula not supported by the final lineamientos.

## 8. Economic value calculation

For each future flow, the engine obtains externally supplied, auditable:

- discount factor for currency/scenario/date;
- FX conversion when reporting currency differs from flow currency.

For a reporting currency `R`:

```text
PV(flow,R) = Amount(flow) * DiscountFactor(flow,scenario) * FX(flow.currency -> R)
```

The EVE identity is:

```text
EVE = PV(Assets) - PV(Liabilities) + PV(Off-Balance net)
```

The engine retains a `DiscountedCashFlow` trace containing the original flow, discount factor, FX rate, present value and signed EVE contribution.

### Floating-rate safeguard

The existing portfolio engine labels future variable coupons projected at the current rate as `PROJECTED_CURRENT_RATE`. Such flows may be used for a transparent base-case projection, but `EconomicValueService` rejects them in stressed scenarios.

Before stressed EVE is calculated, an approved `ScenarioCashFlowProjector` must transform scenario-sensitive floating coupons into scenario-consistent flows. This prevents AIP from shocking only the discount curve while incorrectly holding future reset coupons at today's rate.

## 9. Delta EVE and worst exposure

For every stress scenario `s`:

```text
DeltaEVE(s) = EVE(s) - EVE(BASE)
Fall(s)     = max(EVE(BASE) - EVE(s), 0)
```

The RTILB economic-value exposure is:

```text
WorstLoss = max(Fall(s)) over the six stresses
ExposureRatio = WorstLoss / Tier1Capital
```

`DeltaEVEExposureService` requires all six standard stresses by default and rejects duplicate/missing scenarios or a non-positive Tier 1 denominator.

## 10. Capital buffer

`CapitalBufferService` does not contain regulatory percentages. It receives a versioned `CapitalBufferSchedule` with ordered inclusive upper bounds and a mandatory open-ended final tier.

This supports proposed, effective and internal schedules without changing calculation code.

## 11. Behavioral optionality

The domain declares a `BehavioralCashFlowModel` port for:

- fixed-rate loan prepayment;
- term-deposit early withdrawal;
- non-maturity deposits;
- other approved behavioral assumptions.

No behavioral percentage is embedded in this blueprint. Future assumptions must be parameterized, versioned, approved and traceable.

A non-maturity deposit is not treated as an overnight contractual maturity merely because it can be withdrawn on demand. It is `INCOMPLETE` for EVE until an approved behavioral strategy is available.

## 12. Data quality and calculation readiness

`IRRBBPositionDataQualityService` classifies each canonical position as:

- `READY`: required source data and approved strategy capabilities are available;
- `INCOMPLETE`: one or more required data/strategy elements are missing;
- `EXCLUDED`: the position has no current exposure under an explicit rule, for example zero principal or contractual maturity at/before the cutoff.

Findings use stable machine-readable codes and preserve the field/reason. The validator distinguishes source completeness from runtime capabilities through `IRRBBValidationContext`.

At minimum, diagnostics cover missing or inconsistent:

- maturity;
- payment structure;
- contractual schedule when required;
- contractual rate/payment frequency for investment schedule generation;
- next repricing and repricing frequency for floating positions;
- current/reference-rate basis;
- scenario-aware floating-rate projection capability;
- behavioral model for non-maturity deposits and material optionality;
- unsupported investment payment frequency;
- origination/repricing dates relative to cutoff and maturity.

This is a calculation gate, not a data-cleaning shortcut. Missing fields remain missing until a legitimate source or approved derivation supplies them.

## 13. Implemented architecture phases

The detailed phase documents in `docs/architecture` are authoritative for the scope and exclusions of each slice. The blueprint summarizes the current architecture state; it does not promote any physical source merely because its integration contracts exist.

### Phase 1 — EVE domain core

Implemented:

- canonical banking-book position and cash-flow models;
- methodology/version objects;
- 19 time buckets;
- base/scenario EVE valuation;
- Delta EVE / worst loss / Tier 1 exposure;
- versioned capital-buffer lookup;
- ports for curves, FX, behavioral models and source repositories.

### Phase 2 — Instrument strategies and readiness

Implemented:

- canonical instrument class and payment structure;
- explicit normalized schedule contract/provider;
- investment adapter over `PortfolioContractualCashFlowService`;
- explicit-schedule builder for credit/deposits/borrowings/off-balance;
- current-rate/scenario-projected cash-flow audit status;
- stressed-EVE protection for stale floating-rate projections;
- data-quality/readiness gateway for missing source fields and missing approved strategies.

### Phase 3 — Scenario repricing and behavioral core

Implemented as a source-agnostic calculation boundary:

- explicit floating-rate coupon projection basis;
- scenario-aware coupon projection contracts;
- parameterized scenario-curve shock boundary;
- restrictive parallel-only shock provider where methodology is sufficiently specified;
- versioned non-maturity-deposit profiles and behavioral cash flows.

Non-parallel supervisory shock formulas, prepayment, early-withdrawal and NMD parameter values remain pending approved methodology/configuration; they are not silently approximated.

### Phase 4A / 4B — Calculation orchestration and passive read model

Implemented:

- BASE plus stress-scenario EVE orchestration;
- defensive scenario cash-flow validation;
- separation of EVE from SUGEF GAP;
- passive `RateRiskReadModel` / presenter boundary;
- scenario, GAP, quality, curve and discounted-flow drill-down structures without financial calculations in the presentation layer.

### Phase 5 / 6 — Data gateway and analysis orchestration

Implemented:

- source-agnostic `IRRBBDataGateway` and normalized snapshot loading;
- exact-cutoff validation and snapshot readiness classification;
- orchestration of calculation-ready positions into scenario EVE;
- independent SUGEF GAP classification/aggregation;
- explicit `NO_DATA`, `BLOCKED`, `CALCULATED` and `CALCULATED_WITH_DATA_GAPS` application states.

### Phase 9 / 11 — Source anti-corruption and certification gates

Implemented:

- source-record envelopes and canonical mapping boundary;
- versioned canonical source-requirement profiles;
- evidence-backed source assessments;
- deterministic `READY`, `INCOMPLETE` and `BLOCKED` certification;
- no implicit promotion of omitted requirements or undocumented derivations.

### Phase 12–15 — Institutional investment-master evidence path

Implemented as a passive, fail-closed path:

- investment-master evidence assessment;
- strict source derivation rules;
- canonical mapper contract/policy boundary;
- batch bridge preserving source lineage and enforcing source certification before mapping.

This path is **not** wired into production RTILB runtime composition.

### Phase 16–18A — Physical-source registry and borrowing-workbook evidence path

Implemented:

- governed institutional physical-source registry;
- borrowing-workbook schema inspector;
- local metadata-only inspection CLI;
- strict discovery/header evidence validation.

The borrowing source remains unassessed for contractual RTILB mapping until real institutional discovery/header evidence is supplied.

### Phase 20–20C — Power BI semantic-model metadata boundary

Implemented for governed `Credito` and `Certificados` semantic models:

- source-neutral semantic-model inspection contracts and port;
- strict metadata-only transfer contract and evidence validator;
- deterministic evidence renderer;
- governed inspection coordinator that binds the requested segment to the exact registered source and rejects source substitution.

No Power BI/Fabric provider adapter, authentication flow, tenant/workspace/model identifier, contractual row extraction or RTILB field mapping is implemented by these phases.

## 14. Current physical-source integration status

| Segment | Governed candidate | Implemented boundary | Current activation status | Blocking gate |
|---|---|---|---|---|
| Investments | Institutional investment master | Evidence assessor, source rules, mapper policy boundary, passive batch bridge | **INCOMPLETE / NOT ACTIVE** | Approved cutoff provenance, mapping policy, principal/payment/optionality semantics, floating reset evidence, rejected-row completeness and benchmark parity |
| Borrowings / obligations | Governed obligations workbook | Registry, schema inspector, safe CLI, strict evidence validator | **BLOCKED / NOT ACTIVE** | Real discovery JSON followed by explicit worksheet/header JSON; Phase 19 must be grounded in that evidence |
| Credit | Power BI semantic model `Credito` | Metadata contracts, validator, renderer and governed coordinator | **BLOCKED / NOT ACTIVE** | Institutional authorization of metadata scanning plus runtime workspace/model identity and real metadata evidence |
| Term deposits | Power BI semantic model `Certificados` | Metadata contracts, validator, renderer and governed coordinator | **BLOCKED / NOT ACTIVE** | Institutional authorization of metadata scanning plus runtime workspace/model identity and real metadata evidence |
| Non-maturity deposits / behavioral assumptions | Versioned behavioral profile contract | Behavioral domain ports/models | **BLOCKED FOR EVE** | Approved methodology, effective-dated parameters and governance evidence |
| Market / Tier 1 supplementary inputs | Injected market/capital ports | Domain/application contracts | **NOT CERTIFIED BY SOURCE-INTEGRATION PHASES** | Approved source profiles for curves, FX/reference rates and Tier 1 capital |

No row in this table should be interpreted as production approval. `READY` at source-certification level, when eventually obtained, remains distinct from record-level data quality, calculation readiness, parity validation and runtime activation.

## 15. Evidence required before the next source-specific slices

### 15.1 Borrowings — unlock Phase 19

Run the existing metadata-only CLI on the institutional workstation against the governed obligations workbook:

```text
python -m aip.product.configured.irrbb.borrowing_workbook_inspection_cli --path "<configured-obligations-workbook>" > borrowing-discovery.json
```

After reviewing the exact worksheet names and identifying the institutional header row explicitly:

```text
python -m aip.product.configured.irrbb.borrowing_workbook_inspection_cli --path "<configured-obligations-workbook>" --sheet "<exact-sheet-name>" --header-row <N> > borrowing-header.json
```

Only those real reports may ground a LIABILITY requirement profile, field evidence assessment or canonical mapping rule. A missing field must remain missing.

### 15.2 Credit and term deposits — unlock the Power BI provider adapter

Before provider-specific implementation, institutional evidence must confirm:

- the authorized metadata-inspection mechanism for Power BI/Fabric;
- that detailed semantic-model metadata scanning is enabled when the selected mechanism requires it;
- the authorized authentication mode, without embedding secrets in source code;
- runtime workspace identity/reference for `Credito`;
- runtime semantic-model/dataset identity/reference for `Credito`;
- runtime workspace identity/reference for `Certificados`;
- runtime semantic-model/dataset identity/reference for `Certificados`;
- real metadata-only inspection evidence sufficient to validate the provider parser.

Tokens, passwords, client secrets and similar credentials must remain in the institutional deployment/secret store and must not be committed to the repository or serialized into inspection evidence.

### 15.3 Investments — unlock production activation

The passive investment bridge must remain outside runtime composition until the institution provides or approves, at minimum:

1. workbook-native cutoff/source-selection provenance;
2. an effective-dated product/classification mapping policy;
3. instrument class, balance-sheet side, payment structure, optionality and principal semantics;
4. contractual reset date/frequency evidence for floating-rate positions;
5. an explicit completeness policy for reader-rejected rows;
6. policy applicability to the requested cutoff;
7. parity tests against an approved institutional benchmark.

## 16. Next implementation sequence

The safe next source-specific work is evidence-driven rather than sequence-driven:

1. **Borrowings:** create Phase 19 only after the real Phase 18 discovery/header reports exist.
2. **Power BI:** create the provider-specific semantic-model adapter only after institutional authorization and runtime model identities exist; raw provider metadata must be reduced to the Phase 20 application snapshot and pass the Phase 20C coordinator before acceptance.
3. **Investments:** activate the existing passive bridge only after its remaining governance and parity gates are satisfied.
4. **Runtime composition:** wire physical sources into the IRRBB application only after source certification, record-level readiness, reconciliation/parity and CI/security gates all pass.

Separate methodology work remains pending for approved non-parallel shock transformations, loan prepayment, term-deposit early withdrawal and NMD assumptions. A separate Delta NII / earnings-perspective engine remains a later calculation phase sharing the canonical position and repricing contracts without mixing its formulas with EVE.
