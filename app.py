# app.py — PRODE WorkTimeAsistem FINAL (festivos automáticos + locales)

import io, re, zipfile, calendar
from datetime import datetime, timedelta, date
from itertools import chain

import pandas as pd
import streamlit as st
import pdfplumber

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ======================================================
# CONFIG
# ======================================================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_DIA = HORAS_SEMANALES / 5

DEFAULT_KEYS = [
    ADMIN_KEY,
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

COLOR_OK = "#e6ffef"
COLOR_WARN = "#fff3cd"
COLOR_BAD = "#f8d7da"

# ======================================================
# HELPERS
# ======================================================
def hhmm(h):
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(a, b):
    for n in range((b - a).days + 1):
        yield a + timedelta(n)

def festivos_nacionales_y_andalucia(year):
    return {
        date(year,1,1),    # Año nuevo
        date(year,1,6),    # Reyes
        date(year,2,28),   # Andalucía
        date(year,5,1),    # Trabajo
        date(year,8,15),   # Asunción
        date(year,10,12),  # Hispanidad
        date(year,11,1),   # Todos los Santos
        date(year,12,6),   # Constitución
        date(year,12,8),   # Inmaculada
        date(year,12,25),  # Navidad
    }

# ======================================================
# PDF PARSER
# ======================================================
def parse_pdf(file):
    rows = []
    emp = None
    rx = re.compile(r"(\d{2})-([a-z]{3})\.-(\d{2}).*?(\d+)H\s*(\d+)M", re.I)
    meses = dict(ene=1,feb=2,mar=3,abr=4,may=5,jun=6,jul=7,ago=8,sep=9,oct=10,nov=11,dic=12)

    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            for l in (p.extract_text() or "").split("\n"):
                if l.startswith("Nombre:"):
                    emp = l.replace("Nombre:", "").strip()
                m = rx.search(l)
                if m and emp:
                    d, mth, y, h, mi = m.groups()
                    fecha = date(2000+int(y), meses[mth.lower()], int(d))
                    rows.append({
                        "nombre": emp,
                        "fecha": fecha,
                        "horas": int(h) + int(mi)/60
                    })
    return pd.DataFrame(rows)

# ======================================================
# STREAMLIT UI
# ======================================================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

with st.expander("📘 Cómo funciona esta herramienta"):
    st.markdown("""
- Subes PDF, Excel o CSV de fichajes  
- Se aplican automáticamente los festivos nacionales y de Andalucía  
- Puedes añadir festivos locales manuales  
- Vacaciones, permisos y bajas no cuentan como “sin fichar”  
- Generas informes individuales y un ZIP con todo
""")

# ======================================================
# SESSION STATE
# ======================================================
if "active" not in st.session_state:
    st.session_state.active = False
    st.session_state.user_keys = DEFAULT_KEYS.copy()
    st.session_state.is_admin = False
    st.session_state.ausencias = {}
    st.session_state.festivos_locales_globales = set()
    st.session_state.festivos_locales_por_empleado = {}

# ======================================================
# LOGIN
# ======================================================
st.sidebar.header("🔐 Acceso")
k = st.sidebar.text_input("Clave", type="password")

if st.sidebar.button("Activar"):
    if k in st.session_state.user_keys:
        st.session_state.active = True
        st.session_state.is_admin = (k == ADMIN_KEY)
        st.sidebar.success("Acceso concedido")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.active:
    st.stop()

# ======================================================
# ADMIN
# ======================================================
if st.session_state.is_admin:
    st.sidebar.subheader("🛠 Administración")

    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir clave"):
        if nueva and nueva not in st.session_state.user_keys:
            st.session_state.user_keys.append(nueva)
            st.sidebar.success("Clave añadida")

    borrar = st.sidebar.selectbox("Eliminar clave", st.session_state.user_keys)
    if st.sidebar.button("Eliminar clave"):
        if borrar != ADMIN_KEY:
            st.session_state.user_keys.remove(borrar)
            st.sidebar.warning("Clave eliminada")

# ======================================================
# UPLOAD
# ======================================================
file = st.file_uploader("Sube PDF / Excel / CSV", type=["pdf","xlsx","xls","csv"])
if not file:
    st.stop()

if file.name.lower().endswith(".pdf"):
    df = parse_pdf(file)
else:
    df = pd.read_excel(file) if file.name.endswith(("xls","xlsx")) else pd.read_csv(file)
    df.columns = ["nombre","fecha","horas"]
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date

st.success(f"Registros cargados: {len(df)}")
empleados = sorted(df["nombre"].unique())
st.dataframe(df)

# ======================================================
# AUSENCIAS
# ======================================================
st.subheader("🏖️ Ausencias")
emp = st.selectbox("Empleado", empleados)
motivo = st.selectbox("Motivo", ["Vacaciones","Permiso","Baja médica"])
rng = st.date_input("Rango", [])
if st.button("Añadir ausencia") and len(rng)==2:
    st.session_state.ausencias.setdefault(emp, {}).setdefault(motivo, []).extend(list(daterange(*rng)))
    st.success("Ausencia registrada")

# ======================================================
# FESTIVOS LOCALES
# ======================================================
st.subheader("📅 Festivos locales")
fest = st.date_input("Fecha festiva", [])
modo = st.radio("Aplicar festivo a:", ["Todos los empleados","Solo empleados seleccionados"])
emps_sel = st.multiselect("Selecciona empleados", empleados)

if st.button("Añadir festivo local") and fest:
    if modo == "Todos los empleados":
        st.session_state.festivos_locales_globales.add(fest)
    else:
        for e in emps_sel:
            st.session_state.festivos_locales_por_empleado.setdefault(e, set()).add(fest)
    st.success("Festivo local añadido")

# ======================================================
# PROCESAR
# ======================================================
if st.button("⚙️ Procesar datos y generar informes"):
    with st.spinner("Procesando y generando informes…"):

        month = df["fecha"].iloc[0].month
        year = df["fecha"].iloc[0].year

        festivos_auto = festivos_nacionales_y_andalucia(year)
        dias = list(daterange(
            date(year,month,1),
            date(year,month,calendar.monthrange(year,month)[1])
        ))

        zip_buffer = io.BytesIO()
        pdfs = {}

        st.subheader("📊 Resumen Global")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for e, g in df.groupby("nombre"):
                mapa = g.groupby("fecha")["horas"].sum().to_dict()
                aus = list(chain.from_iterable(st.session_state.ausencias.get(e, {}).values()))
                fest = (
                    festivos_auto |
                    st.session_state.festivos_locales_globales |
                    st.session_state.festivos_locales_por_empleado.get(e, set())
                )

                laborables = [d for d in dias if d.weekday()<5 and d not in aus and d not in fest]
                objetivo = len(laborables)*HORAS_DIA
                total = sum(mapa.values())
                sin = len([d for d in laborables if d not in mapa])

                color = COLOR_OK if sin<=2 else COLOR_WARN if sin<=4 else COLOR_BAD
                st.markdown(
                    f"<div style='background:{color};padding:8px'>"
                    f"<b>{e}</b> — Total {hhmm(total)} | Objetivo {hhmm(objetivo)} | Sin fichar {sin} días</div>",
                    unsafe_allow_html=True
                )

                buf = io.BytesIO()
                doc = SimpleDocTemplate(buf, pagesize=A4)
                doc.build([Paragraph(f"{e} — {month}/{year}", getSampleStyleSheet()["Title"])])
                buf.seek(0)

                pdfs[e] = buf
                zipf.writestr(f"{year}-{month:02d}/{e}.pdf", buf.getvalue())

        zip_buffer.seek(0)

        for e,b in pdfs.items():
            st.download_button(f"📄 Descargar {e}", b.getvalue(), f"{e}.pdf", "application/pdf")

        st.download_button(
            "📦 Descargar TODO en ZIP",
            zip_buffer.getvalue(),
            f"PRODE_WorkTimeAsistem_{year}_{month:02d}.zip",
            "application/zip"
        )

        st.success("Informes generados correctamente")

# ======================================================
# LEYENDA
# ======================================================
st.subheader("🎨 Leyenda")
st.markdown(f"""
<div style="background:{COLOR_OK};padding:6px">✔ Normal (≤2 días sin fichar)</div>
<div style="background:{COLOR_WARN};padding:6px">⚠ Atención (3–4 días)</div>
<div style="background:{COLOR_BAD};padding:6px">❌ Crítico (>4 días)</div>
""", unsafe_allow_html=True)






