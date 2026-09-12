# SUGEF standard IRRBB GAP template — 2023 supervisory workbook

## Purpose and governance

This document records the business rules observed in the SUGEF workbook titled
**“Método estándar para medir el riesgo de tasa de interés en el libro bancario”**,
whose instructions request information with cutoff at 31 October 2023.

The workbook is treated as a **supervisory template/source artifact**. It is not used
as evidence that the January 2024 prospective VEP/Delta-EVE methodology became an
effective regulation. AIP therefore keeps the SUGEF 2023 repricing-GAP view separate
from the prospective VEP/EVE methodology and from internal Basel-aligned analytics.

## Scope stated by the workbook

The template asks for interest-rate-sensitive banking-book assets and liabilities and
excludes the trading portfolio. Its instructions identify, at minimum:

- investment portfolio, excluding the trading portfolio / investment-fund participations;
- credit portfolio;
- term and sight obligations with the public;
- obligations with BCCR;
- obligations with financial entities;
- interest-rate hedging derivatives.

The workbook also provides accounting-account families for reconciliation, including
122–128 for investments, 131–138 for credit, 211/213/219 for public obligations,
221/222/228 for BCCR obligations, and 231/232/233/238 for obligations with financial
and non-financial entities.

The presence of accounting accounts is treated as a reconciliation requirement, not
as a substitute for contractual cash-flow data.

## Reporting currency and currency split

The workbook contains separate **Plantilla MN** and **Plantilla ME** sheets.

The instructions require reported balances in Costa Rican colones without cents.
Foreign-currency amounts are converted using the BCCR reference **selling exchange
rate at month-end**. Development Units are converted to the month-end value in colones
reported by BCCR.

AIP must therefore preserve both:

1. the native contractual currency used by IRRBB calculations; and
2. the supervisory reporting amount in CRC together with the conversion source/date.

The MN/ME classification must not be inferred from the already converted CRC amount.
It must preserve the original currency group.

## Nineteen time bands

The exact display labels in the workbook are:

1. Overnight
2. 1 día a 1 mes
3. 1 a 3 meses
4. 3 a 6 meses
5. 6 a 9 meses
6. 9 a 12 meses
7. 1 a 1.5 años
8. 1.5 a 2 años
9. 2 a 3 años
10. 3 a 4 años
11. 4 a 5 años
12. 5 a 6 años
13. 6 a 7 años
14. 7 a 8 años
15. 8 a 9 años
16. 9 a 10 años
17. 10 a 15 años
18. 15 a 20 años
19. Más de 20 años

`IRRBBTimeBucketService` uses calendar-month boundaries and exposes these labels.

## Supervisory row taxonomy

### Assets

- Portafolio de inversiones, tasa fija
- Portafolio de inversiones, tasa variable / semivariable
- Cartera de crédito, tasa fija
- Cartera de crédito, tasa variable / semivariable

### Liabilities

For each relevant counterparty family, the workbook separates sight obligations with
and without financial cost and term obligations by fixed versus variable/semivariable
rate:

- obligaciones con el público;
- obligaciones with BCCR;
- obligaciones with financial entities.

Exact mapping of account 233 and any additional non-financial-entity classification
must remain configuration/data-dictionary driven; AIP must not infer a row solely from
a textual account description.

## Contractual-flow rule for fixed-rate positions

Fixed-rate instruments are assigned according to the contractual payment date of each
remaining cash flow.

The SUGEF examples demonstrate that:

- a zero-coupon security is placed at maturity for the total amount receivable,
  including principal and interest paid at maturity;
- a coupon security places each coupon in its payment band and the final coupon plus
  principal in the maturity band;
- a fixed-rate amortizing loan places every remaining installment, including principal
  and interest, in its contractual payment band.

## Repricing rule for variable and semivariable positions

The variable-rate loan example materially constrains the implementation.

For a position that reprices before final maturity:

1. contractual payments due **before or at the next repricing date** remain assigned to
   their contractual payment bands;
2. the **outstanding principal immediately after the payment at the repricing date** is
   assigned to the band containing the next repricing date;
3. contractual installments and interest amounts after that repricing date are **not**
   carried forward at the current rate merely to fill the GAP template.

This rule means that a generic implementation such as
`risk_date = min(payment_date, next_repricing_date)` applied to every future installment
is not sufficient: it would incorrectly accumulate post-reset interest and installments
at the reset date.

AIP therefore implements the SUGEF GAP view through a dedicated
`SugefStandardGapService` and `SugefGapExposure` model, separate from `IRRBBCashFlow`
used by VEP/EVE.

For amortizing floating-rate positions, the normalized schedule must provide enough
principal information to determine principal outstanding at repricing. This can be an
explicit `outstanding_principal_after` balance or sufficient principal components to
derive it. Missing principal runoff data is a data-quality failure; AIP does not invent
an amortization convention.

Semivariable credit is operationally represented by the first contractual
`next_repricing_date`: payments before that date are treated as fixed and residual
principal is exposed at the first reset.

## Acceptance examples captured as automated tests

The SUGEF examples are treated as golden acceptance cases:

- Example A — zero-coupon security: CRC 1,210,000 in 9–12 months.
- Example B — coupon security: CRC 16,250; 32,500; 48,750; and 1,548,750 across the
  1-day–1-month, 1–3-month, 3–6-month and 6–9-month bands.
- Example C — fixed-rate loan: CRC 254,479; 508,958; 763,437; 763,437; 763,437; and
  1,272,395 through the 1–1.5-year band.
- Example D — variable-rate loan: CRC 254,479; 508,958; and 3,256,087, with the last
  amount consisting of the payments due through reset plus outstanding principal at
  repricing.
- Example E — semivariable loan: same banding as the supplied example D because the
  first reset date is the same in that case.

These tests validate the methodology independently from XML, SQL, Excel or OneDrive
source adapters.

## Optionality and non-maturity deposits

The workbook asks additional questions about:

- policies governing loan prepayments and early cancellation of obligations; and
- analyses of the impact of those options.

However, the supplied workbook does **not** specify a quantitative behavioral maturity
or decay model for sight / non-maturity deposits, nor a numerical prepayment or early
withdrawal assumption.

AIP must therefore continue to classify those calculations as incomplete until an
approved methodology/parameter set is supplied. It must not automatically place all
non-maturity deposits in Overnight merely because they are withdrawable on demand.

## Derivatives

The instructions state that interest-rate hedging derivatives should be included, but
the visible MN/ME row taxonomy in the supplied workbook does not provide an explicit
derivative row. The domain retains off-balance/derivative capability, but the final
supervisory-row mapping must be confirmed from the corresponding data dictionary or
lineamiento rather than invented.

## Separation from VEP / Delta EVE

The 2023 workbook defines a repricing/cash-flow GAP view. It does not, by itself, define:

- the six shocked yield-curve transformations;
- scenario discounting formulas;
- Delta EVE / VEP calculation;
- the Tier 1 exposure denominator mechanics; or
- capital-buffer thresholds.

Those components remain versioned under their own approved/prospective methodology.
The same source contracts may feed both views, but the calculation objects are kept
separate to prevent a GAP shortcut from contaminating VEP/EVE valuation.
