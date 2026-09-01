from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class TableExportService:
    def export_records(
        self, path: Path | str, *, headers: list[str], rows: list[list[Any]], export_format: str
    ) -> str:
        target = Path(path)
        if export_format == "csv":
            target = target.with_suffix(".csv")
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                writer.writerows(rows)
        elif export_format == "json":
            target = target.with_suffix(".json")
            payload = [{header: value for header, value in zip(headers, row)} for row in rows]
            target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        elif export_format == "excel":
            target = target.with_suffix(".xlsx")
            target.write_text("", encoding="utf-8")
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        return str(target)
