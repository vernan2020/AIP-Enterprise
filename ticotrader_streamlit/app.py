"""Run from the repository root: streamlit run ticotrader_streamlit/app.py."""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st  # noqa: E402

from ticotrader_streamlit.access import authorize  # noqa: E402
from ticotrader_streamlit.catalog import COMPARISON_SERIES, load_entities  # noqa: E402
from ticotrader_streamlit.jobs import Jobs  # noqa: E402
from ticotrader_streamlit.views import show  # noqa: E402
from ticotrader_web.forecast_policy import FORECAST_INDICATORS  # noqa: E402

st.set_page_config(page_title="TicoTrader Atlas", page_icon="📊", layout="wide")
st.title("TicoTrader Atlas")
st.caption("Inteligencia financiera y macroeconómica · Acceso privado")
try:
    settings = st.secrets.to_dict()
except st.errors.StreamlitSecretNotFoundError:
    settings = {}
if not settings.get("auth") or not settings.get("atlas"):
    st.info(
        "El administrador debe completar la configuración privada antes de habilitar el acceso."
    )
    st.stop()
if not st.user.is_logged_in:
    st.button("Ingresar con Google", on_click=st.login, type="primary")
    st.stop()
try:
    owner, admin = authorize(dict(st.user), settings["atlas"], settings["auth"].get("client_id"))
except (PermissionError, ValueError) as exc:
    st.error(str(exc))
    st.button("Cerrar sesión", on_click=st.logout)
    st.stop()


@st.cache_resource(max_entries=1)
def queue(token, email):
    return Jobs({"token": token, "email": email})


bccr = settings.get("bccr", {})
jobs = queue(bccr.get("token", ""), bccr.get("email", ""))
with st.sidebar:
    st.write(owner)
    st.caption("Administrador" if admin else "Consulta")
    page = st.radio(
        "Sección",
        [
            "Análisis financiero",
            "Inteligencia macroeconómica",
            "Forecast Lab",
            "Comparativo histórico",
            "Escenario aprobado",
        ]
        + (["Administración"] if admin else []),
    )
    st.button("Cerrar sesión", on_click=st.logout)

if page == "Administración":
    st.success("Token BCCR configurado" if bccr.get("token") else "Token BCCR pendiente")
    st.write("Usuarios autorizados:", len(settings["atlas"]["allowed_emails"]))
    st.info(
        "Las credenciales y los accesos se administran desde Settings → Secrets en Streamlit. No se muestran ni se editan tokens en esta pantalla."
    )
    st.stop()
kind = {
    "Análisis financiero": "financial",
    "Inteligencia macroeconómica": "macro",
    "Forecast Lab": "forecast",
    "Comparativo histórico": "compare",
    "Escenario aprobado": "projection",
}[page]
st.subheader(page)
query = {"kind": kind}
financial_data = {}
if st.session_state.get("job_financial"):
    try:
        previous = jobs.read(owner, st.session_state["job_financial"])
        financial_data = previous.get("data", {})
    except KeyError:
        pass
entities = {str(code): name for code, name in financial_data.get("entities", [])}
if kind in ("financial", "compare"):
    try:
        with st.spinner("Cargando nombres de entidades desde SUGEF…"):
            entities = load_entities()
    except Exception:
        if entities:
            st.warning("SUGEF no respondió. Se usa el catálogo de tu última consulta.")
        else:
            st.warning("No fue posible cargar las entidades desde SUGEF.")
            if st.button("Reintentar carga de entidades"):
                load_entities.clear()
                st.rerun()
            st.stop()
with st.form("query"):
    if kind == "financial":
        if entities:
            query["entity_id"] = st.selectbox("Entidad", list(entities), format_func=entities.get)
        else:
            query["entity_id"] = None
            st.caption(
                "La primera consulta carga la entidad predeterminada y el catálogo de entidades."
            )
        query["cutoff"] = st.date_input("Fecha de corte", date.today()).isoformat()
    elif kind == "forecast":
        query["indicator"] = st.selectbox("Indicador", FORECAST_INDICATORS)
        st.caption("Seleccioná una TRI por moneda y plazo. No se calculan todas simultáneamente.")
    elif kind == "compare":
        query["entity_ids"] = st.multiselect(
            "Entidades",
            list(entities),
            format_func=entities.get,
            max_selections=5,
            help="Escribí parte del nombre y seleccioná hasta cinco entidades.",
        )
        series = {
            item["code"]: item.get("label", item["code"])
            for item in financial_data.get("metric_history", [])
            + financial_data.get("statement_history", [])
        }
        series = {**COMPARISON_SERIES, **series}
        query["series_code"] = st.selectbox("Serie", list(series), format_func=series.get)
        query["horizon"] = st.selectbox("Horizonte", ["12M", "24M", "36M", "5Y", "ALL", "CUSTOM"])
        start = st.date_input("Desde (para CUSTOM)", date(2023, 1, 1))
        end = st.date_input("Hasta", date.today())
        query["custom_from"] = start.isoformat() if query["horizon"] == "CUSTOM" else None
        query["custom_to"] = end.isoformat()
    query["refresh"] = (
        st.checkbox("Actualizar desde la fuente", disabled=not admin) if admin else False
    )
    submitted = st.form_submit_button("Consultar", type="primary")
if submitted:
    try:
        st.session_state[f"job_{kind}"] = jobs.submit(owner, query, admin)
    except (ValueError, PermissionError):
        st.error(
            "Revisá los parámetros: de una a cinco entidades, fechas válidas y hasta dos consultas pendientes."
        )


@st.fragment(run_every=2)
def waiting(job_id):
    try:
        result = jobs.read(owner, job_id)
        if result["status"] != "running":
            st.rerun()
        st.info("Consulta en cola o en ejecución. Podés navegar entre secciones.")
    except KeyError:
        st.warning("La consulta venció; volvé a consultar.")


job_id = st.session_state.get(f"job_{kind}")
if job_id:
    try:
        result = jobs.read(owner, job_id)
        if result["status"] == "running":
            waiting(job_id)
        elif result["status"] == "error":
            st.error(result["message"])
        else:
            show(result["data"], kind)
    except KeyError:
        st.info("La consulta venció; volvé a consultar.")
else:
    st.info(
        "Iniciá una consulta. Se muestran únicamente datos disponibles de las fuentes oficiales."
    )
