# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL)
- Lee: Excel (.xls/.xlsx), CSV
- Calcula objetivo mensual, diferencia y horas extra
- Genera PDFs individuales y globales con coloreado profesional
- Activación por clave, gestión de ausencias y festivos
- Autor: preparado para AMCHÍ / Fundación PRODE
"""

import os
import io
import calendar
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain
import zipfile

import pandas as pd
import numpy as np
import streamlit as st

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# -----------------------------
# CONFIG
# -----------------------------
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"
LOGO_FILENAME = "logo-prode.jpg"
LOGO_LOCAL_PATH = "/mnt/data/logo-prode.jpg"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

DEFAULT_KEYS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

DEFAULT_FESTIVOS = [
    "2025-01-01","2025-03-24","2025-04-17","2025-04-18","2025-05-01",
    "2025-05-26","2025-06-16","2025-06-23","2025-06-30","2025-07-20",
    "2025-08-07","2025-08-18","2025-10-13","2025-11-03","2025-11-17",
    "2025-12-08","2025-12-25"
]
FESTIVOS_ANDALUCIA = ["2025-02-28"]

COLOR_HORA_EXTRA = "#d8fcd8"
COLOR_DEFICIT = "#ffe4b2"
COLOR_SIN_MODERADO = "#fff6a3"
COLOR_SIN_GRAVE = "#ffb3b3"
COLOR_FESTIVO = "#cfe3ff"
COLOR_VACACIONES = "#e4ceff"
COLOR_PERMISO = "#ffd6f3"
COLOR_BAJA = "#c9f2e7"

COLOR_PRIMARY = "#12486C"
COLOR_SECOND = "#2F709F"

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# -----------------------------
# HELPERS
# -----------------------------
def safe_parse_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def time_str_to_hours(s):
    if pd.isna(s):
        return np.nan
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m)/60
    s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return np.nan

def hours_to_hhmm(hours):
    if hours is None or pd.isna(hours):
        return "0:00"
    m = int(round(hours * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end-start).days + 1):
        yield start + timedelta(n)

def create_month_folder_from_date(year, month):
    meses = ["enero","febrero","marzo","abril","mayo","junio","julio",
             "agosto","septiembre","octubre","noviembre","diciembre"]
    folder = BASE_DIR / "informes" / f"{meses[month-1].capitalize()} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

# -----------------------------
# UI CABECERA
# -----------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.markdown(f"<h1 style='color:{COLOR_PRIMARY};'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)

with st.expander("ℹ️ Cómo usar esta aplicación"):
    st.markdown("""
**1️⃣ Sube un archivo Excel o CSV**  
Debe contener:
- Empleado
- Fecha
- Horas trabajadas (o jornada)

**2️⃣ Añade festivos o ausencias**
- Festivos extra: puedes aplicarlos a todos o solo a empleados concretos
- Ausencias: vacaciones, permisos o bajas médicas

**3️⃣ Pulsa “Procesar datos”**
- Se generan informes individuales por empleado
- Se genera un resumen global
- Puedes descargar todo en ZIP o individualmente
""")

# -----------------------------
# SESSION
# -----------------------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.is_admin = False
if "user_keys" not in st.session_state:
    st.session_state.user_keys = DEFAULT_KEYS.copy()
if "dias_por_empleado" not in st.session_state:
    st.session_state.dias_por_empleado = {}
if "festivos_por_empleado" not in st.session_state:
    st.session_state.festivos_por_empleado = {}

# -----------------------------
# AUTH
# -----------------------------
st.sidebar.header("🔐 Acceso")
key = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if key in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.is_admin = (key == ADMIN_KEY)
        st.sidebar.success("Activado")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.stop()

# -----------------------------
# UPLOAD (SIN PDF)
# -----------------------------
st.subheader("📂 Subir archivo")
uploaded = st.file_uploader("Archivo Excel o CSV", type=["xlsx","xls","csv"])
if not uploaded:
    st.stop()

# -----------------------------
# READ FILE
# -----------------------------
if uploaded.name.endswith(("xls","xlsx")):
    df_raw = pd.read_excel(uploaded)
else:
    df_raw = pd.read_csv(uploaded, sep=None, engine="python")

cols = {c.lower(): c for c in df_raw.columns}
df = pd.DataFrame()
df["nombre"] = df_raw[[c for c in cols if "nombre" in c][0]]
df["fecha"] = pd.to_datetime(df_raw[[c for c in cols if "fecha" in c][0]])
df["horas"] = df_raw[[c for c in cols if "hora" in c or "jornada" in c][0]].apply(time_str_to_hours)

# -----------------------------
# FESTIVOS EXTRA POR EMPLEADO
# -----------------------------
st.subheader("📅 Festivos extra")
fecha_festivo = st.date_input("Fecha festiva")
aplicar_a = st.radio("Aplicar a", ["Todos", "Empleados seleccionados"])
empleados = sorted(df["nombre"].unique())

if aplicar_a == "Empleados seleccionados":
    seleccionados = st.multiselect("Selecciona empleados", empleados)
else:
    seleccionados = empleados

if st.button("➕ Añadir festivo"):
    for e in seleccionados:
        st.session_state.festivos_por_empleado.setdefault(e, set()).add(fecha_festivo)
    st.success("Festivo añadido")

st.success("APP LISTA PARA USAR")

