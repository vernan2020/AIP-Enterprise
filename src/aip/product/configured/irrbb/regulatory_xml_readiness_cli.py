from __future__ import annotations

import argparse
import json
from datetime import date

from aip.product.configured.configuration.institutional_paths import expand_environment_path
from aip.product.configured.irrbb.regulatory_financial_xml import RegulatoryFinancialXMLReader
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def main(argv: list[str] | None = None) -> int:
    """Inspect the configured institutional XML sources without modifying them."""
    parser = argparse.ArgumentParser(description="Diagnóstico XML Brechas / Calce RTILB")
    parser.add_argument("--cutoff", required=True, help="Fecha de cierre YYYY-MM-DD")
    args = parser.parse_args(argv)
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("--cutoff requiere YYYY-MM-DD")
    config = EnvironmentLoader().load_source_config().xml_confia
    if not config.enabled or not config.root:
        print(json.dumps({
            "status": "UNCONFIGURED",
            "detail": "XML CONFIA no habilitado o sin raíz de origen.",
        }, ensure_ascii=False))
        return 2

    resolved = expand_environment_path(config.root)
    if not resolved:
        print(json.dumps({"status": "UNCONFIGURED"}, ensure_ascii=False))
        return 2

    snapshot = RegulatoryFinancialXMLReader(resolved).load(cutoff_date=cutoff)
    print(json.dumps({
        "cutoff": cutoff.isoformat(),
        "status": "VALIDATED" if snapshot.is_valid else "BLOCKED",
        "files": [
            {
                "filename": item.filename,
                "status": item.status,
                "period": item.period.isoformat() if item.period else None,
                "entity_id": item.entity_id,
                "rows": len(item.rows) if item.is_valid else None,
                "account_totals": len(item.account_totals) if item.is_valid else None,
                "sha256": item.source_sha256,
                "issues": list(item.issues),
            }
            for item in snapshot.files
        ],
    }, indent=2, ensure_ascii=False))
    return 0 if snapshot.is_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
