# Policy Engine

The policy engine provides deterministic evaluation semantics for domain policies, including
composite operators, dependency resolution, severity ordering, and registry lookup.

## Highlights

- Immutable policy context and result models
- Boolean-style composition with AND, OR, and NOT policies
- Dependency-aware evaluation with short-circuit behavior
- In-memory registry for dynamic registration and lookup
- Traceable evaluation results with timestamps and context identifiers
