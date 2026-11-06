import io
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def table(rows):
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("No hay datos disponibles para esta sección.")


def chart(points, fields, x="iso_date", title="Evolución"):
    if not points:
        return
    frame = pd.DataFrame(points)
    if x not in frame:
        return
    fig = go.Figure()
    for field in fields:
        if field in frame:
            values = pd.to_numeric(frame[field], errors="coerce")
            fig.add_trace(
                go.Scatter(
                    x=frame[x], y=values, name=field, mode="lines+markers", connectgaps=False
                )
            )
    fig.update_layout(title=title, height=360, margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(fig, width="stretch")


def history(series, key):
    if series:
        index = st.selectbox(
            "Serie histórica",
            range(len(series)),
            format_func=lambda i: series[i].get("label", series[i].get("code", str(i))),
            key=key,
        )
        item = series[index]
        chart(item.get("points", []), ["value"], title=item.get("label", "Evolución"))
        table(item.get("points", []))


def diagnostics(data):
    for key in (
        "status",
        "source",
        "source_name",
        "cutoff_date",
        "forecast_origin",
        "freshness_notice",
        "diagnostic",
        "diagnostics",
        "warnings",
        "rating_methodology",
    ):
        if data.get(key):
            st.write(f"**{key}:**", data[key])


def workbook(data):
    from openpyxl import Workbook

    from ticotrader_web.contracts import safe_cell

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws.append(["Campo", "Valor"])
    for name, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            sheet = wb.create_sheet(name[:31])
            keys = list(dict.fromkeys(k for row in value for k in row))
            sheet.append(keys)
            for row in value:
                sheet.append([safe_cell(row.get(k)) for k in keys])
            sheet.freeze_panes = "A2"
        else:
            ws.append([name, safe_cell(value)])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def show(data, kind):
    if kind == "financial":
        tabs = st.tabs(
            ["Estados y cuentas", "Comparativo", "KPIs históricos", "Calificación", "Trazabilidad"]
        )
        with tabs[0]:
            table(data.get("statement_rows"))
            history(data.get("statement_history"), "statement_history")
        with tabs[1]:
            table(data.get("peer_rows"))
        with tabs[2]:
            table(data.get("metrics"))
            history(data.get("metric_history"), "metric_history")
        with tabs[3]:
            st.write("Calificación:", data.get("rating_grade", "N/D"))
            for key in (
                "peer_rating_rows",
                "rating_dimensions",
                "rating_indicators",
                "indicator_reconciliations",
            ):
                st.caption(key)
                table(data.get(key))
        with tabs[4]:
            diagnostics(data)
    elif kind == "macro":
        tabs = st.tabs(["Matriz macro", "Curvas TRI", "Trazabilidad"])
        with tabs[0]:
            table(data.get("market_snapshot"))
        with tabs[1]:
            for currency in ("crc", "usd"):
                rows = data.get(f"tri_{currency}_curve", [])
                chart(rows, ["value", "previous_value"], "tenor", f"TRI {currency.upper()}")
                table(rows)
        with tabs[2]:
            diagnostics(data)
    elif kind == "forecast":
        st.caption("Perfil ligero · NAIVE, DRIFT, AR(1), AR(2) · No es un escenario aprobado")
        tabs = st.tabs(["Proyección", "Modelos y métricas", "Ensemble", "Trazabilidad"])
        with tabs[0]:
            st.write("Modelo seleccionado:", data.get("champion_model", "N/D"))
            chart(
                data.get("points", []),
                ["forecast", "lower_80", "upper_80", "lower_95", "upper_95"],
                "period",
                "Proyección e intervalos",
            )
            table(data.get("points"))
        with tabs[1]:
            table(data.get("models"))
        with tabs[2]:
            table(data.get("ensemble"))
        with tabs[3]:
            diagnostics(data)
    elif kind == "compare":
        for entity in data.get("entities", []):
            chart(entity.get("points", []), ["value"], title=entity.get("entity_name", "Entidad"))
            table(entity.get("points"))
        diagnostics(data)
    elif (
        kind == "projection"
        and data.get("status") == "UNAVAILABLE"
        and data.get("diagnostic") == "No approved institutional macro scenario is available"
    ):
        st.info("Todavía no hay un escenario macroeconómico aprobado disponible en Atlas.")
    else:
        table(data.get("rows"))
        diagnostics(data)
    st.download_button(
        "Descargar Excel",
        workbook(data),
        f"Atlas_{kind}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button(
        "Descargar datos JSON",
        json.dumps(data, ensure_ascii=False, indent=2),
        f"Atlas_{kind}.json",
        "application/json",
    )
