# IRRBB Phase 21 — Delta NII domain core

## Purpose

Phase 21 introduces the source-agnostic earnings-perspective calculation core for IRRBB without activating any physical source, projecting new business, or embedding an institutional balance-sheet assumption.

The objective is deliberately narrower than a full NII simulator. This phase accepts explicit, auditable interest accruals that have already been produced by an approved projection strategy and then:

1. converts them into one reporting currency using an NII-specific FX port;
2. aggregates projected interest income and interest expense for one scenario;
3. calculates net interest income (NII); and
4. compares BASE with an explicitly required stress set to produce Delta NII and the worst fall from base.

No source adapter or UI is added by this phase.

## Methodological reference

The current Basel Framework distinguishes the earnings perspective from EVE and defines Delta NII as the change between projected NII in a base scenario and an alternative stressed scenario. Current Basel disclosure guidance uses a forward-looking rolling 12-month period, constant balance-sheet assumption and instantaneous shock, while the standardised IRRBB framework prescribes parallel-up and parallel-down scenarios for NII.

Phase 21 does **not** hardcode those choices. The projection horizon, balance-sheet assumption, shock timing, methodology version and required scenario set are explicit inputs so Coopealianza can later support an effective local methodology, Basel-aligned internal methodology or other approved policy without changing the calculation formula.

References:

- Basel Framework `SRP98.52–98.53` — earnings-based IRRBB measures;
- Basel Framework `SRP31.90` — standardised NII shock-scenario scope;
- Basel Framework `DIS70` / IRRBB1 — Delta NII disclosure definition.

## Projection basis

`NIIProjectionBasis` carries the common comparison perimeter:

- versioned `IRRBBMethodologyProfile`;
- valuation date;
- explicit horizon end date;
- balance-sheet assumption: `RUN_OFF`, `CONSTANT` or `DYNAMIC`;
- shock timing: `INSTANTANEOUS`, `GRADUAL` or `OTHER`;
- source/reference trace for the approved projection input.

The horizon must be strictly forward-looking. The domain does not infer 12 months, one year, month-end or any other horizon from the valuation date.

BASE and stressed NII results must use exactly the same projection basis before Delta NII can be calculated.

## Explicit NII accrual contract

`NIIInterestAccrual` represents one projected interest amount and preserves:

- stable accrual identifier;
- position identifier;
- scenario;
- `INTEREST_INCOME` or `INTEREST_EXPENSE` classification;
- amount and native currency;
- accrual start/end dates;
- source reference;
- amount status;
- optional repricing trace;
- optional projection-basis trace.

Amounts are allowed to be negative. This is intentional because negative-rate environments can produce negative interest income or negative interest expense; the domain must preserve the supplied economic sign rather than force every interest amount to be positive.

The service calculates:

```text
NII = sum(interest income) - sum(interest expense)
```

No principal cash flow, fee, commission or non-interest income is silently included.

## Rate-projected accruals and repricing coherence

An accrual marked `RATE_PROJECTED` must provide both:

- `NIIRepricingTrace`; and
- a nonblank `projection_basis` reference.

`NIIRepricingTrace` records:

- rate/reference identifier;
- contractual or modeled repricing date;
- pricing tenor in months;
- applied rate;
- source reference.

The domain does not reconstruct the applied rate from a curve, index, spread, floor or cap in this phase.

A repricing date cannot occur after the start of the accrual period represented by the same record. If a position reprices inside an accrual period, the projection layer must split that period at the repricing boundary and submit separate accruals. This prevents one record from hiding two different rate bases or tenors.

## NII-specific FX boundary

Projected future earnings do not automatically use the EVE spot-FX convention.

`NIIExchangeRateProvider` receives:

- source currency;
- reporting currency;
- scenario;
- valuation date; and
- accrual end date.

The approved NII methodology therefore owns the FX conversion assumption explicitly. Same-currency translation uses the mathematical identity `1`; cross-currency accruals fail closed if no provider is supplied or if the provider returns a non-positive rate.

## NetInterestIncomeService

The service accepts one scenario's explicit accruals and applies defensive controls:

- at least one accrual is required;
- accrual IDs must be unique;
- every accrual scenario must equal the requested calculation scenario;
- no accrual may start before the valuation date;
- no accrual may end after the explicit projection horizon;
- cross-currency conversion requires the NII FX port;
- no rounding convention, repricing rule or business-replacement assumption is invented.

The output `NetInterestIncomeResult` retains every converted accrual with its FX rate and signed NII contribution.

## DeltaNIIService

`DeltaNIIService` compares one BASE result with an explicitly required stress set.

It does not contain a default scenario list. The caller must provide the scenario set approved by the selected methodology.

Controls:

- BASE result must use the BASE scenario;
- required stress set cannot be empty, duplicated or contain BASE;
- all results must use the same reporting currency;
- all results must use exactly the same `NIIProjectionBasis`;
- missing required scenarios fail;
- unexpected scenarios fail;
- duplicate stressed scenarios fail.

For each stress `s`:

```text
DeltaNII(s) = NII(s) - NII(BASE)
Fall(s)     = max(NII(BASE) - NII(s), 0)
```

The worst scenario is the scenario with the largest fall from BASE.

## Explicitly not implemented

Phase 21 does not yet decide or implement:

1. how existing contractual schedules become NII accrual periods;
2. constant-balance-sheet replacement mechanics;
3. dynamic balance-sheet growth or corporate-plan projections;
4. run-off assumptions;
5. future reference-rate or FTP curve construction;
6. margins/spreads for replacement transactions;
7. loan prepayment or deposit early-withdrawal behavior;
8. NMD earnings behavior;
9. cross-currency FX forecasting methodology;
10. SUGEF-specific Delta NII shock magnitudes or limits;
11. physical-source adapters;
12. runtime/UI composition.

These must remain separate, versioned and evidence-backed.

## Next safe phase

The next source-neutral slice may introduce an `NIIProjectionProvider` / strategy boundary that transforms certified `BankingBookPosition` and contractual schedule inputs into the explicit `NIIInterestAccrual` contract.

That future phase must preserve this separation:

```text
Certified banking-book positions / schedules
                  |
                  v
       Approved NII projection strategy
                  |
      +-----------+-----------+
      |                       |
      v                       v
 BASE NII accruals      stressed NII accruals
      |                       |
      +-----------+-----------+
                  v
       NetInterestIncomeService
                  |
                  v
          DeltaNIIService
```

A projection strategy is not permitted to manufacture missing contractual repricing terms merely to obtain a calculated result.
