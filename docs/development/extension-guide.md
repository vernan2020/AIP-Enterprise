# Extension Guide

Extensions should remain isolated from core business logic and should expose narrow integration points.

## Principles

- Keep domain behavior in the extension package.
- Reuse shared services and models where possible.
- Prefer configuration-driven behavior over hard-coded rules.
- Add unit tests for any new branch or integration point.
