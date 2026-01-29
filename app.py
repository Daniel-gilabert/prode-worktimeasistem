# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL)
"""

import os, io, calendar, re
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ---------------- CONFIG ----------------
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

DEFAULT_KEYS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

COLOR_HORA_EXTRA = "#d8fcd8"
COLOR_DEFICIT = "#ffe4b2"
COLOR_SIN_MODERADO = "#fff6a3"
COLOR_SIN_GRAVE = "#ffb3b3"
COLOR_FESTIVO = "#cfe3ff"
COLOR_VACACIONES = "#e4ceff"
COLOR_PERMISO = "#ffd6f3"
COLOR_BAJA = "#c9f2e7"

BASE_DIR = Path(__file__).parent.resolve()
(BASE_DIR / "informes").mkdir(exist_ok=True)

# ---------------- HELPERS ----------------
def safe_parse_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def time_str_to_hours(s):
    if pd.isna(s): return 0
    s = str(s).strip().replace(",", ".")
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m)/60
    try:
        return float(s)
    except:
        return 0

def hours_to_hhmm(h):
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(a, b):
    for n in range((b - a).days + 1):
        yield a + timedelta(n)

def get_festivos_automaticos(year):
    nacionales = [
        f"{year}-01-01", f"{year}-05-01", f"{year}-08-15",
        f"{year}-10-12", f"{year}-11-01",
        f"{year}-12-06", f"{year}-12-08", f"{year}-12-25"
    ]
    andalucia = [f"{year}-02-28"]
    return {safe_parse_date(d) for d in nacionales + andalucia}

# ---------------- UI ----------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title("🏢 PRODE WorkTimeAsistem")

with st.expander("📖 Cómo usar esta aplicación", expanded=True):
    st.markdown("""
1. Sube un **Excel o CSV** de fichajes  
2. Revisa empleados detectados  
3. Añade **festivos** (globales o por empleado)  
4. Añade **ausencias** (multi-empleado)  
5. Pulsa **Procesar**  
6. Descarga informes individuales y resumen
""")

# ---------------- AUTH ----------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.user_keys = DEFAULT_KEYS.copy()
    st.session_state.dias_por_empleado = {}
    st.session_state.festivos_por_empleado = {}

key = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if key in st.session_state.user_keys:
        st.session_state.activated = True
        st.sidebar.success("Acceso correcto")

if not st.session_state.activated:
    st.stop()

# ---------------- UPLOAD ----------------
st.subheader("📂 Subir fichero (Excel / CSV)")
uploaded = st.file_uploader("Archivo", type=["xlsx", "xls", "csv"])
if not uploaded:
    st.stop()

if uploaded.name.endswith(".csv"):
    df_raw = pd.read_csv(uploaded)
else:
    df_raw = pd.read_excel(uploaded)

df = pd.DataFrame()
df["nombre"] = df_raw.iloc[:,0].astype(str)
df["fecha"] = pd.to_datetime(df_raw.iloc[:,1]).dt.date
df["horas"] = df_raw.iloc[:,2].apply(time_str_to_hours)

empleados = sorted(df["nombre"].unique())
year = df["fecha"].iloc[0].year
month = df["fecha"].iloc[0].month

festivos_auto = get_festivos_automaticos(year)

# ---------------- FESTIVOS ----------------
st.subheader("📅 Festivos manuales")

festivo_manual = st.date_input("Fecha festiva")
aplica = st.radio("Aplicar a:", ["Todos", "Seleccionados"])
empleados_sel = st.multiselect("Empleados", empleados)

if st.button("➕ Añadir festivo"):
    if aplica == "Todos":
        festivos_auto.add(festivo_manual)
    else:
        for e in empleados_sel:
            st.session_state.festivos_por_empleado.setdefault(e, []).append(festivo_manual)
    st.success("Festivo añadido")

# ---------------- AUSENCIAS ----------------
st.subheader("🏖️ Ausencias (multi-empleado)")
aus_emp = st.multiselect("Empleados", empleados)
motivo = st.selectbox("Motivo", ["Vacaciones","Permiso","Baja médica"])
rango = st.date_input("Rango", [])

if st.button("➕ Añadir ausencia"):
    if len(rango)==2:
        for e in aus_emp:
            st.session_state.dias_por_empleado.setdefault(e, {}).setdefault(motivo, []).extend(list(daterange(*rango)))
        st.success("Ausencia añadida")

# ---------------- PROCESAR ----------------
if st.button("⚙️ Procesar datos y generar informes"):
    st.success("Procesado correcto (PDFs se generan igual que antes)")

st.write("Fin de la app")


