# Coopealianza Liquidity Extension

This extension provides institution-specific liquidity policy evaluation for Coopealianza.
It reuses the existing Policy Engine, HQLA Foundation, liquidity foundation, liquidity gap engine, and analytics explainability components from the core domain layer instead of re-implementing them.

## Responsibilities

- Typed immutable configuration for institutional liquidity policies
- Reusable policy implementations built on the existing policy abstractions
- Provider ports for portfolio assets and institutional policy data
- Deterministic liquidity policy reporting and explainability

No ICL, IFNE, EML, or RL calculations are implemented in this sprint.
