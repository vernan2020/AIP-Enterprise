# IRRBB / RTILB Domain Blueprint

## 1. Purpose

This document defines the source-independent domain core for **Interest Rate Risk in the Banking Book (IRRBB / RTILB)** in AIP Enterprise.

The first implementation intentionally covers the **economic value perspective (VEP / EVE)** only. Data connectors, database technology and PySide6 views are outside this boundary. A later NII/margin engine will share the same canonical position, repricing and behavioral assumptions without mixing its calculation rules with EVE.

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
                       v
          RepricingCashFlowBuilder
                       |
              +--------+--------+
              |                 |
              v                 v
     Contractual schedules   Behavioral model
              |                 |
              +--------+--------+
                       v
                 IRRBBCashFlow
                       |
                       v
              19 time buckets
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
- currency;
- principal and optional carrying amount;
- fixed/floating classification;
- contractual rate, reference rate and spread when available;
- maturity;
- next repricing date and repricing frequency;
- payment frequency;
- optionality classification;
- source trace/reference.

Missing mandatory information is not silently imputed.

## 5. Cash-flow ownership

Instrument-specific cash-flow builders own contractual schedule generation. The generic IRRBB engine consumes canonical `IRRBBCashFlow` objects and does not recreate instrument calendars.

For investments, the adapter **must reuse/adapt `PortfolioContractualCashFlowService`**, which is already the canonical AIP portfolio coupon/principal schedule. A second investment coupon calendar is prohibited.

`IRRBBCashFlow` distinguishes:

- `cashflow_date`: contractual/behavioral payment date;
- `risk_date`: date selected by the repricing strategy for interest-rate-risk mapping.

This distinction prevents a floating-rate instrument with long contractual maturity from being treated as if its entire repricing exposure remained at final maturity.

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

## 12. Data quality rules

The future application layer must classify each input position/cash flow as ready, incomplete or excluded. Required information must never be silently estimated merely to produce a number.

At minimum, diagnostics must identify missing:

- maturity;
- next repricing for floating positions;
- payment/repricing frequency where required;
- contractual rate/reference/spread where required;
- currency;
- source trace;
- curve/discount factor;
- FX conversion;
- Tier 1 capital.

## 13. Future phases

### Phase 2 — Instrument strategies

Adapters/builders for investments, credit, deposits, borrowings and off-balance positions.

### Phase 3 — Behavioral IRRBB

Versioned prepayment, early-withdrawal and non-maturity-deposit models.

### Phase 4 — Application/UI

Dashboard with EVE base, worst Delta EVE, Delta EVE/Tier 1, scenarios, 19-band heatmap, curve visualization, drill-down and data-quality panel.

### Phase 5 — Source adapters

OneDrive, SQL Server, regulatory XML, Excel, PostgreSQL or any combination selected by the institution.

### Phase 6 — NII / earnings perspective

A separate Delta NII engine sharing the canonical positions, repricing dates, curves and behavioral assumptions, while preserving calculation separation from EVE.
