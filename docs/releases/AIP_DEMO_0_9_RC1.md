# AIP Enterprise Demo 0.9 RC1

## Objective

Release Candidate 1 for the integrated demo experience of AIP Enterprise. The release focuses on an operational, visually demonstrable desktop experience with deterministic demo data, read-only workflows, and a stable startup path.

## Included Workspaces

- Executive workspace as the default landing page.
- Portfolio workspace with deterministic rows and summaries.
- Market workspace with curve and relative-value views.
- Liquidity workspace with deterministic gaps and capacity views.
- Treasury workspace with read-only recommendation context.
- System Status panel for core platform components.

## Execution Mode

- Default: Demo Mode.
- Safe fallback: Demo Mode is used when no production configuration is present.
- Configured-source mode remains available through the existing configuration loader.

## Start Command

```bash
python src/aip/main.py
```

## Demo Dataset

The release uses deterministic demo data for portfolio, market, liquidity, and executive views. The values are synthetic and read-only by design.

## Refresh All

Refresh All runs a single application-wide refresh with one correlation ID and updates the visible workspaces and status panel. The UI exposes completion and correlation information through the shell status bar.

## Status Interpretation

- HEALTHY: healthy demo status.
- DEGRADED: a reduced-capability state.
- UNAVAILABLE: not available in the current demo configuration.
- DISABLED: intentionally inactive.
- UNKNOWN: no verified state.

## Known Limitations

- Screenshots are created only when the environment supports a desktop display.
- Windows packaging is scaffolded but full binary validation requires a Windows host.

## Packaging Status

A packaging foundation is present under the repository packaging scaffold and can be used to produce a Windows executable with PyInstaller.

## Next Release Objectives

- Expand the UI smoke coverage for additional navigation and refresh scenarios.
- Add richer system-status diagnostics.
- Prepare a final Windows packaging validation pass on a Windows host.
