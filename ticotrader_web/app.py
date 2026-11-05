"""Private web API. One process serializes the inherited mutable desktop runtime."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import math
import os
import secrets
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from ticotrader_web import connections
from ticotrader_web.forecast_policy import FORECAST_INDICATORS
from ticotrader_web.runtime import Runtime

ROOT = Path(__file__).parent

INDICATORS = FORECAST_INDICATORS


def clean(value):
    if is_dataclass(value):
        return clean(asdict(value))
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def safe_cell(value):
    value = (
        json.dumps(clean(value), ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


class BCCRConnection(BaseModel):
    token: str = Field(min_length=8, max_length=4096)
    email: str = Field(default="", max_length=254)
    name: str = Field(default="TicoTrader", max_length=100)


class Query(BaseModel):
    kind: Literal["financial", "compare", "macro", "projection", "forecast"]
    entity_id: str | None = Field(default=None, max_length=80)
    cutoff: date | None = None
    refresh: bool = False
    entity_ids: list[str] = Field(default_factory=list, max_length=5)
    series_code: str = Field(default="ASSETS", max_length=160)
    horizon: Literal["12M", "24M", "36M", "5Y", "ALL", "CUSTOM"] = "36M"
    custom_from: date | None = None
    custom_to: date | None = None
    indicator: str = "TBP"

    @model_validator(mode="after")
    def validate_query(self):
        if self.indicator not in INDICATORS:
            raise ValueError("Indicador no admitido")
        if self.kind == "compare":
            if not self.entity_ids:
                raise ValueError("Seleccione de una a cinco entidades")
            if self.horizon == "CUSTOM" and (not self.custom_from or not self.custom_to):
                raise ValueError("Seleccione ambas fechas")
            if self.custom_from and self.custom_to and self.custom_from > self.custom_to:
                raise ValueError("Desde no puede ser posterior a Hasta")
        return self


def create_app(runtime=None):
    app = FastAPI(
        title="TicoTrader Atlas · Inteligencia Financiera",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv("TICOTRADER_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(
            ","
        ),
    )
    engine = runtime or Runtime()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ticotrader")
    jobs = OrderedDict()
    guard = Lock()
    attempts = OrderedDict()
    sessions = {}
    username = os.getenv("TICOTRADER_USERNAME", "")
    password_hash = os.getenv("TICOTRADER_PASSWORD_HASH", "")
    secure = os.getenv("TICOTRADER_COOKIE_SECURE", "true").lower() == "true"

    def verify_password(password):
        try:
            scheme, iterations, salt, expected = password_hash.split("$")
            if scheme != "pbkdf2_sha256":
                return False
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
            ).hex()
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    def authenticated(request: Request):
        sid = request.cookies.get("tt_session", "")
        with guard:
            session = sessions.get(sid)
        if not session or session["expiry"] < time.time():
            raise HTTPException(401, "Inicie sesión")
        if request.method not in ("GET", "HEAD") and not hmac.compare_digest(
            request.headers.get("x-csrf-token", ""), session["csrf"]
        ):
            raise HTTPException(403, "Sesión de formulario no válida")
        return sid

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "TicoTrader"}

    @app.post("/api/login")
    def login(body: Login, request: Request, response: Response):
        if not username or not password_hash:
            raise HTTPException(503, "El administrador debe configurar el acceso privado.")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Origen no permitido")
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        with guard:
            for key in [key for key, v in sessions.items() if v["expiry"] < now]:
                sessions.pop(key, None)
            recent = [t for t in attempts.get(ip, []) if now - t < 900]
            if len(recent) >= 5:
                raise HTTPException(429, "Demasiados intentos. Reintente en 15 minutos.")
            attempts[ip] = recent + [now]
            while len(attempts) > 1000:
                attempts.popitem(last=False)
        if not hmac.compare_digest(body.username, username) or not verify_password(body.password):
            raise HTTPException(401, "Usuario o contraseña incorrectos")
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with guard:
            attempts.pop(ip, None)
            sessions[sid] = {"expiry": now + 28800, "csrf": csrf}
        response.set_cookie(
            "tt_session", sid, httponly=True, secure=secure, samesite="strict", max_age=28800
        )
        return {"username": username, "csrf": csrf}

    @app.get("/api/session")
    def session(sid=Depends(authenticated)):
        return {"username": username, "csrf": sessions[sid]["csrf"], "indicators": INDICATORS}

    @app.post("/api/logout")
    def logout(response: Response, sid=Depends(authenticated)):
        with guard:
            sessions.pop(sid, None)
        response.delete_cookie("tt_session")
        return {"status": "ok"}

    @app.get("/api/connections")
    def get_connections(sid=Depends(authenticated)):
        return connections.status()

    @app.post("/api/connections/bccr")
    def save_connection(body: BCCRConnection, sid=Depends(authenticated)):
        with engine.lock:
            connections.write(body.token.strip(), body.email.strip(), body.name.strip())
            engine._factory = None
        return connections.status()

    def execute(query):
        with engine.lock:
            if query.kind == "financial":
                result = engine.financial(query.entity_id, query.cutoff, query.refresh)
            elif query.kind == "compare":
                result = engine.compare(
                    query.entity_ids,
                    query.series_code,
                    query.horizon,
                    query.custom_from,
                    query.custom_to,
                )
            elif query.kind == "macro":
                result = engine.macro(query.refresh)
            elif query.kind == "projection":
                result = engine.projection()
            else:
                result = engine.forecast(query.indicator, query.refresh)
        return connections.redact(clean(result))

    @app.post("/api/jobs")
    def submit(query: Query, sid=Depends(authenticated)):
        with guard:
            expired = [
                key
                for key, j in jobs.items()
                if time.time() - j["created"] > 3600 and j["future"].done()
            ]
            for key in expired:
                jobs.pop(key, None)
            # Deduplicate active identical queries and bound queued work.
            for key, j in jobs.items():
                if j["owner"] == sid and j["query"] == query and not j["future"].done():
                    return {"id": key}
            if sum(not j["future"].done() for j in jobs.values()) >= 4:
                raise HTTPException(429, "Hay consultas en curso; espere a que finalicen.")
            while len(jobs) >= 100:
                completed = next((key for key, j in jobs.items() if j["future"].done()), None)
                if completed is None:
                    break
                jobs.pop(completed)
            key = secrets.token_urlsafe(18)
            jobs[key] = {
                "owner": sid,
                "query": query,
                "created": time.time(),
                "future": executor.submit(execute, query),
            }
        return {"id": key}

    def get_job(key, sid):
        with guard:
            job = jobs.get(key)
        if job is None or job["owner"] != sid:
            raise HTTPException(404, "Consulta no encontrada")
        return job

    @app.get("/api/jobs/{key}")
    def status(key: str, sid=Depends(authenticated)):
        job = get_job(key, sid)
        if not job["future"].done():
            return {"status": "running"}
        try:
            return {"status": "complete", "data": job["future"].result()}
        except Exception:
            # Provider exceptions can include URLs/credentials; do not expose them.
            return {
                "status": "error",
                "message": "No se pudo consultar la fuente. Revise la configuración del servidor y la disponibilidad del proveedor.",
            }

    @app.get("/api/jobs/{key}/export")
    def export(
        key: str, format: Literal["xlsx", "csv", "json"] = "xlsx", sid=Depends(authenticated)
    ):
        job = get_job(key, sid)
        if not job["future"].done():
            raise HTTPException(409, "Consulta en proceso")
        try:
            data = job["future"].result()
        except Exception:
            raise HTTPException(409, "La consulta no tiene resultados exportables")
        filename = "TicoTrader_Atlas_" + job["query"].kind
        if format == "json":
            return Response(
                json.dumps(data, ensure_ascii=False, indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
            )
        tables = {
            k: v for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)
        }
        metadata = [{"campo": k, "valor": v} for k, v in data.items() if not isinstance(v, list)]
        tables = {"Resumen": metadata, **tables}
        if format == "csv":
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            for name, rows in tables.items():
                writer.writerow([name])
                keys = list(dict.fromkeys(k for row in rows for k in row))
                writer.writerow(keys)
                writer.writerows([[safe_cell(row.get(k)) for k in keys] for row in rows])
                writer.writerow([])
            return Response(
                "\ufeff" + output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
            )
        from openpyxl import Workbook
        from openpyxl.chart import LineChart, Reference
        from openpyxl.styles import Font, PatternFill

        wb = Workbook()
        wb.remove(wb.active)
        for name, rows in tables.items():
            ws = wb.create_sheet(name[:31])
            keys = list(dict.fromkeys(k for row in rows for k in row))
            ws.append(keys)
            for row in rows:
                ws.append([safe_cell(row.get(k)) for k in keys])
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.font = Font(color="FFFFFF", bold=True)
                cell.fill = PatternFill("solid", fgColor="123E55")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(
                    65, max(18, max(len(str(c.value or "")) for c in col) + 2)
                )
        # Expand nested time series to numeric chartable sheets.
        series = (
            data.get("metric_history", [])
            + data.get("statement_history", [])
            + data.get("entities", [])
        )
        for i, series_item in enumerate(series):
            if not isinstance(series_item, dict) or not series_item.get("points"):
                continue
            ws = wb.create_sheet(f"Serie {i+1}")
            ws.append(["Fecha", series_item.get("label", series_item.get("entity_name", "Valor"))])
            for point in series_item["points"]:
                ws.append([point.get("iso_date"), point.get("value")])
            chart = LineChart()
            chart.title = str(series_item.get("label", series_item.get("entity_name", "Serie")))[
                :100
            ]
            chart.add_data(
                Reference(ws, min_col=2, min_row=1, max_row=ws.max_row), titles_from_data=True
            )
            chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
            ws.add_chart(chart, "D2")
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    app.state.executor = executor
    return app


app = create_app()
