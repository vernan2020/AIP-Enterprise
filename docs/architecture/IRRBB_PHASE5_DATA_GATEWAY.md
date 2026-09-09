# IRRBB Phase 5 — Application / Data Gateway

## Objective

Phase 5 establishes the source-agnostic application boundary used to feed the RTILB/IRRBB module without coupling the domain or PySide6 UI to SQL Server, SUGEF XML, PostgreSQL, Excel/OneDrive or any other physical source.

## Boundary

`IRRBBDataGateway` exposes one operation: load a normalized snapshot for a requested cutoff date. A physical adapter must translate its native schema into canonical IRRBB domain objects before crossing this boundary.

The normalized snapshot contains:

- canonical `BankingBookPosition` records;
- runtime validation capabilities through `IRRBBValidationContext`;
- optional SUGEF GAP schedules and routing metadata;
- optional auditable curve source points;
- explicit source references.

No physical source field names are admitted into the application contract.

## Load use case

`LoadIRRBBSourceSnapshot` performs only source-perimeter and readiness work:

1. requests the exact valuation cutoff from the gateway;
2. rejects a snapshot returned for another cutoff;
3. runs the domain `IRRBBPositionDataQualityService` for every canonical position;
4. classifies the snapshot as `EMPTY`, `READY`, `PARTIAL` or `BLOCKED`;
5. exposes the exact ready, incomplete and excluded position identifiers.

It does **not** calculate VEP/EVE, Delta VEP, SUGEF GAP, discount factors, shocked curves, optionality or behavioral cash flows.

## Adapter rule

Future adapters may read from SUGEF XML, SQL Server, PostgreSQL, Excel/OneDrive or another approved source, but they must all implement the same gateway contract. Source precedence and reconciliation must be explicit and auditable; no adapter may silently invent missing maturity, repricing, schedule, rate, curve or behavioral assumptions.

## Next phase

Phase 6 will compose this validated source result with the already-certified IRRBB domain services: scenario cash-flow providers, curve/discount-factor ports, Tier 1 capital, SUGEF GAP calculation and the passive UI presenter/read-model.
