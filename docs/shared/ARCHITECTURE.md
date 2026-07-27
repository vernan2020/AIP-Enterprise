# Shared Foundation Architecture

## Purpose

The Shared Foundation centralizes cross-cutting domain primitives and utilities used by business modules in AIP Enterprise. It reduces duplication, enforces consistency, and protects financial correctness.

## Layer Position

Shared Foundation sits below domain modules and above language/runtime primitives.

- Upstream users: domain aggregates, services, application handlers.
- Downstream dependencies: Python standard library (`decimal`, `datetime`, `json`, `enum`, `dataclasses`).

## Module Responsibilities

- `validation`: input contracts and typed validation failures.
- `math`: deterministic arithmetic utilities for financial computations.
- `conventions`: finance standards for accrual and scheduling logic.
- `calendars`: market/business-day rules with holiday calendars.
- `dates`: business-aware date abstractions and period operations.
- `money`: monetary value object model and FX conversion.
- `serialization`: lossless JSON handling for numeric/date domain values.
- `collections`: immutable containers for safe sharing and hashing.

Calendar policy note:
- Costa Rica holiday logic separates statutory national holidays from institutional/banking closures.
- August 2 is treated as an opt-in institutional holiday, not a universal national banking holiday.
- Institutional closures are configurable by year via injected holiday providers.

## Dependency Direction

Dependency flow is one-way and acyclic at module intent level:

- `money` -> `validation`
- `math` -> `validation`
- `conventions` -> `datetime`, `decimal`
- `dates` -> `calendars`, `conventions`
- `serialization` -> `json`, `decimal`, `datetime`
- `collections` -> typing/runtime only

Shared modules avoid importing application or UI layers.

## Key Design Decisions

1. Decimal over float

All monetary and rate calculations use `Decimal` to preserve financial precision and deterministic rounding behavior.

2. Value-object immutability

Domain primitives are immutable (`frozen=True` where applicable) to guarantee referential safety and hashability.

3. Typed validation exceptions

Validation failures are explicit and class-based, enabling precise error mapping at service boundaries.

4. Convention-driven date logic

Day-count and business-day behavior is represented as typed conventions and calendars, not ad-hoc conditionals.

5. Serializer precision preservation

`Decimal` values are serialized as strings to avoid loss when crossing JSON boundaries.

## Behavioral Guarantees

- Money operations require currency compatibility.
- Business-day adjustments follow explicit conventions.
- Date and decimal conversions are deterministic.
- Immutable collections return defensive, non-mutating projections.

## Quality Baseline

- Full shared test suite green.
- Coverage for `src/aip/shared` at 97%.
- No placeholder code (`TODO`, `pass`) in shared foundation implementation.

## Future Extensions

- Additional market calendars by jurisdiction.
- Explicit FX quote conventions (direct/indirect quote metadata).
- Serialization adapters for external schema contracts.
- Performance tuning for high-volume schedule generation.
