"""Credential-safe, read-only direct check of SDDE v2 from institutional Windows."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector.sdde_v2_client import SDDEv2Client
from aip.product.demo.configuration.environment_loader import EnvironmentLoader

_CODES = ("317", "318", "3541", "423")


def _latest_valid_observation(payload: dict, code: str) -> dict[str, str] | None:
    candidates: list[tuple[date, Decimal]] = []
    for indicator in payload["body"]["datos"]:
        if not isinstance(indicator, dict):
            continue
        if str(indicator.get("codigoIndicador")) != code:
            continue
        for item in indicator.get("series", []):
            if not isinstance(item, dict):
                continue
            try:
                observed = date.fromisoformat(str(item["fecha"])[:10])
                amount = Decimal(str(item["valorDatoPorPeriodo"]))
            except (KeyError, TypeError, ValueError, InvalidOperation):
                continue
            if amount.is_finite() and observed <= date.today():
                candidates.append((observed, amount))
    if not candidates:
        return None
    asof, value = max(candidates, key=lambda item: item[0])
    return {"date": asof.isoformat(), "value": str(value)}


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BCCR SDDE v2 direct live verification")
    parser.add_argument("--dry-run", action="store_true", help="Validate identity without HTTP")
    parser.add_argument("--codes", nargs="+", choices=_CODES, default=list(_CODES))
    parser.add_argument("--days", type=int, default=32)
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")

    settings = EnvironmentLoader().load_source_config().bccr
    report: dict = {
        "source": "BCCR/SDDE/REST/v2",
        "host": "apim.bccr.fi.cr",
        "name_configured": bool(settings.name),
        "email_configured": bool(settings.email),
        "bearer_configured": bool(settings.token),
        "request_mode": "READ_ONLY",
        "indicators": [],
    }
    if not settings.enabled or not settings.token:
        report["status"] = "UNCONFIGURED"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    client = None
    try:
        client = SDDEv2Client(
            config=BCCRConfig(
                base_url=settings.base_url or "https://apim.bccr.fi.cr",
                name=settings.name,
                email=settings.email,
                token=settings.token,
                timeout_seconds=settings.timeout_seconds,
                retry_attempts=min(settings.retries, 2),
            )
        )
        if args.dry_run:
            report["status"] = "READY_FOR_LIVE_TEST"
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        today = date.today()
        start = (today - timedelta(days=args.days)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
        for code in args.codes:
            try:
                response = client.fetch_series(indicator_code=code, from_date=start, to_date=end)
                observation = _latest_valid_observation(response, code)
                record = {"code": code, "status": "LIVE_OK" if observation else "NO_OBSERVATIONS"}
                if observation is not None:
                    record.update(observation)
                report["indicators"].append(record)
            except (ConnectionError, TimeoutError, ValueError, OSError) as exc:
                # The new client never includes credentials in its errors.
                # Avoid echoing any raw exception or HTTP response body.
                details = str(exc)
                http_status = next(
                    (
                        item
                        for item in ("401", "403", "404", "429", "500", "502", "503", "504")
                        if f"HTTP {item}" in details
                    ),
                    None,
                )
                report["indicators"].append(
                    {
                        "code": code,
                        "status": "HTTP_ERROR" if http_status else "ERROR",
                        "http_status": http_status,
                        "type": type(exc).__name__,
                    }
                )

        report["status"] = (
            "LIVE_OK"
            if all(item["status"] == "LIVE_OK" for item in report["indicators"])
            else "PARTIAL_OR_BLOCKED"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "LIVE_OK" else 2
    except (ValueError, OSError, ConnectionError) as exc:
        report["status"] = "CONFIGURATION_ERROR"
        report["error_type"] = type(exc).__name__
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(run())
