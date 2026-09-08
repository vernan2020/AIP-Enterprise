# Portfolio Characterization Gate

This gate captures the current Desktop RC1 behavior required by the approved AIP Enterprise Web shared-domain strategy before any physical Financial Core extraction is authorized.

## Scope

Focused characterization covers:

- HQLA eligibility and haircuts
- MIL collateral eligibility
- DV01 calculation and policy exclusions
- institutional DV01 buckets
- parallel rate shocks
- stable security identity / aggregation keys

## Focused execution evidence

An isolated reproduction of the exact target services and characterization tests was executed with:

- Python 3.13.5
- pytest 9.0.2

Result:

```text
31 passed, 1 xfailed
```

The single expected xfail is the general institutional HQLA policy that classifications whose code starts with `V.C` must be excluded. The current `PortfolioHQLAService` does not yet enforce that rule generically.

## Important limitation

This is focused execution evidence, not a full-repository regression run. The PR must remain separate from any production methodology correction until the `V.C` rule is implemented and the complete Desktop regression/parity gates are executed.

## Extraction status

`AIP-Financial-Core` physical creation/extraction remains NOT AUTHORIZED by this gate alone.
