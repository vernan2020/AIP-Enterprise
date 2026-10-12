from __future__ import annotations

import argparse
import json
from datetime import date

from aip.product.configured.configuration.institutional_paths import expand_environment_path
from aip.product.configured.irrbb.regulatory_financial_xml import RegulatoryFinancialXMLReader
from aip.product.configured.irrbb.regulatory_gap_six_band import build_regulatory_gap
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def main(argv: list[str] | None = None) -> int:
    """Inspect the configured institutional XML sources without modifying them."""
    parser = argparse.ArgumentParser(description="Diagnóstico XML Brechas / Calce RTILB")
    parser.add_argument("--cutoff", help="Fecha de cierre YYYY-MM-DD (modo histórico)")
    parser.add_argument("--latest", action="store_true", help="Último mes guardado (predeterminado)")
    args = parser.parse_args(argv)
    if args.cutoff and args.latest:
        parser.error("Use --cutoff o --latest, pero no ambos.")
    cutoff = None
    if args.cutoff:
        try:
            cutoff = date.fromisoformat(args.cutoff)
        except ValueError:
            parser.error("--cutoff requiere YYYY-MM-DD")
    config = EnvironmentLoader().load_source_config().xml_confia
    if not config.enabled or not config.root:
        print(
            json.dumps(
                {
                    "status": "UNCONFIGURED",
                    "detail": "XML CONFIA no habilitado o sin raíz de origen.",
                },
                ensure_ascii=False,
            )
        )
        return 2

    resolved = expand_environment_path(config.root)
    if not resolved:
        print(json.dumps({"status": "UNCONFIGURED"}, ensure_ascii=False))
        return 2

    reader = RegulatoryFinancialXMLReader(resolved)
    snapshot = (
        reader.load(cutoff_date=cutoff)
        if cutoff is not None
        else reader.load_latest(reference_cutoff=date.today())
    )
    gap = build_regulatory_gap(snapshot)
    print(
        json.dumps(
            {
                "mode": "FIXED_CUTOFF" if cutoff is not None else "LATEST_SAVED",
                "source_month": snapshot.cutoff_date.strftime("%Y-%m")
                if any(item.period for item in snapshot.files) else None,
                "status": "VALIDATED" if snapshot.is_valid else "BLOCKED",
                "six_band_gap": {
                    "status": gap.status,
                    "bucket_count": len(gap.rows),
                    "issues": list(gap.issues),
                    "cumulative_gap_crc": str(gap.rows[-1].cumulative_gap_crc)
                    if gap.is_ready else None,
                },
                "files": [
                    {
                        "filename": item.filename,
                        "status": item.status,
                        "period": item.period.isoformat() if item.period else None,
                        "entity_id": item.entity_id,
                        "load_type": item.load_type,
                        "rows": len(item.rows) if item.is_valid else None,
                        "account_totals": len(item.account_totals) if item.is_valid else None,
                        "sha256": item.source_sha256,
                        "issues": list(item.issues),
                    }
                    for item in snapshot.files
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if snapshot.is_valid and gap.is_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
