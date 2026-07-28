# Application Layer

This package contains the internal application orchestration layer for AIP Enterprise.

## Responsibilities

- coordinate existing domain engines without embedding business logic
- preserve deterministic execution order
- collect execution telemetry and workflow lifecycle events
- expose simple contracts for workflow input and output

## Layers

- Contracts: workflow request/result DTOs
- Workflows: orchestration for a single analysis pathway
- Orchestrators: entry points for wider business scenarios
- Events: lifecycle dispatching for workflow events
- Telemetry: execution metrics for auditing and observability
