# AIP Enterprise RC1 — Final Runtime Checkpoint

Checkpoint integral del runtime institucional consolidado al 2026-09-01.

- Branch: `recovery/full-runtime-rc1-20260829`
- Archive: `aip_final_runtime_20260901.tar.gz`
- SHA-256: `c52dad620c82c8ef7cce6c1d1314ad3d66325a7822aa009c3f8338e31fbb867d`
- Archive bytes: `486072`
- Base64 chars: `648096`
- Runtime members: `933`
- Expected parts: `8` (`runtime_src.part00.b64` through `runtime_src.part07.b64`)

The archive contains the complete production `src/` runtime plus `run_aip_configured.cmd`. It excludes Python bytecode, local backup files, virtual environments, databases, caches and credentials.

Validation before checkpoint sealing:

- `python -m compileall -q src`: PASS
- Liquidity / MIL / stress / treasury decision / relative-value pure-domain suites: 166 PASS
- Reconstructed archive SHA-256: PASS
- Reconstructed archive compileall: PASS
- UI synthetic/demo marker audit: 0 findings

Runtime secrets (including BCCR credentials) are intentionally not committed. They remain runtime environment configuration only.
