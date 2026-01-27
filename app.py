# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL)
- Lee: Excel (.xls/.xlsx), CSV, PDF (Informe de Control de Presencia)
- Analiza registros generados por sistemas externos de fichaje
- NO registra fichajes
- NO modifica datos de origen
- Cumple art. 34.9 ET (analizador auditable)
- Incluye selector de año (ejercicio), festivos locales manuales
- PDFs con identificación clara de ejercicio
- Autor: preparado para AMCHÍ / Fundación PRODE
"""

import os
import io
import calendar
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

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

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7

DEFAULT_KEYS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

# Festivos 2026 (España + Andalucía)
DEFAULT_FESTIVOS = [
    "2026-01-01","2026-01-06","2026-04-03","2026-05-01",
    "2026-08-15","2026-10-12","2026-12-08","2026-12-25"
]
FESTIVOS_ANDALUCIA = ["2026-02-28","2026-04-02"]

# Colores
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
    s = str(s).replace(",", ".").strip()
    try:
        return float(s)
    except:
        return np.nan

def hours_to_hhmm(hours):
    if hours is None or (isinstance(hours, float) and np.isnan(hours)):
        return "0:00"
    total_min = int(round(float(hours) * 60))
    return f"{total_min//60}:{total_min%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

def create_month_folder_from_date(year, month):
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    folder = BASE_DIR / "informes" / f"{meses[month-1].capitalize()} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.markdown(f"<h1 style='color:{COLOR_PRIMARY};'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:gray;'>"
    "Analizador auditable · NO registra fichajes · NO modifica datos de origen"
    "</p>",
    unsafe_allow_html=True
)
st.markdown("---")

# -----------------------------
# SESSION & AUTH
# -----------------------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.current_key = ""
    st.session_state.is_admin = False
if "user_keys" not in st.session_state:
    st.session_state.user_keys = DEFAULT_KEYS.copy()
if "dias_por_empleado" not in st.session_state:
    st.session_state.dias_por_empleado = {}

st.sidebar.header("🔐 Acceso")
key_input = st.sidebar.text_input("Introduce tu clave:", type="password")
if st.sidebar.button("Activar"):
    if key_input.strip() in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.current_key = key_input.strip()
        st.session_state.is_admin = (key_input.strip() == ADMIN_KEY)
        st.sidebar.success("Activado ✅")
    else:
        st.sidebar.error("Clave inválida")

if not st.session_state.activated:
    st.warning("Activa la aplicación con tu clave para continuar.")
    st.stop()

# -----------------------------
# UPLOAD
# -----------------------------
st.subheader("📂 Subir archivo de fichajes (Excel oficial)")
uploaded = st.file_uploader("Selecciona el archivo", type=["xlsx", "xls"])
if not uploaded:
    st.stop()

# -----------------------------
# READ EXCEL (FORMATO OFICIAL)
# -----------------------------
df_raw = pd.read_excel(uploaded)
cols = {c.lower().strip(): c for c in df_raw.columns}

def find_col(posibles):
    for p in posibles:
        for k, orig in cols.items():
            if p in k:
                return orig
    return None

col_nombre = find_col(["apellidos y nombre", "apellidos", "nombre"])
col_fecha = find_col(["fecha"])
col_horas = find_col(["tiempo trabajado"])

if not col_nombre or not col_fecha or not col_horas:
    st.error("❌ El Excel no coincide con el formato oficial.")
    st.error(f"Columnas encontradas: {list(df_raw.columns)}")
    st.stop()

df = pd.DataFrame()
df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce", dayfirst=True).dt.date
df["horas"] = pd.to_numeric(df_raw[col_horas], errors="coerce")
df = df.dropna(subset=["nombre", "fecha", "horas"])

st.success(f"Registros cargados: {len(df)}")

# -----------------------------
# SELECTOR DE AÑO (EJERCICIO)
# -----------------------------
anio_detectado = int(df["fecha"].apply(lambda d: d.year).mode()[0])
anios_disponibles = sorted(df["fecha"].apply(lambda d: d.year).unique())

st.sidebar.markdown("### 📅 Ejercicio")
YEAR_EJERCICIO = st.sidebar.selectbox(
    "Año",
    options=anios_disponibles,
    index=anios_disponibles.index(anio_detectado)
)

df = df[df["fecha"].apply(lambda d: d.year) == YEAR_EJERCICIO]

# -----------------------------
# PERIODO
# -----------------------------
month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
year = YEAR_EJERCICIO
month_name = ["enero","febrero","marzo","abril","mayo","junio",
              "julio","agosto","septiembre","octubre","noviembre","diciembre"][month-1].capitalize()

folder = create_month_folder_from_date(year, month)

# -----------------------------
# FESTIVOS (POR AÑO)
# -----------------------------
st.subheader("📅 Festivos locales / municipales (manual)")
st.caption("Añade aquí festivos locales que no estén en el calendario nacional o autonómico.")

festivos_input = st.text_input("Fechas (AAAA-MM-DD, separadas por coma)")
manual_festivos = [safe_parse_date(f) for f in festivos_input.split(",") if safe_parse_date(f)]

festivos_objetivos = {
    safe_parse_date(f) for f in DEFAULT_FESTIVOS
    if safe_parse_date(f) and safe_parse_date(f).year == year
}
festivos_objetivos |= {
    safe_parse_date(f) for f in FESTIVOS_ANDALUCIA
    if safe_parse_date(f) and safe_parse_date(f).year == year
}
festivos_objetivos |= {f for f in manual_festivos if f and f.year == year}

# -----------------------------
# PROCESADO (IGUAL QUE TENÍAS)
# -----------------------------
if st.button("⚙️ Procesar datos y generar informes"):
    resumen = []

    dias_mes = list(daterange(
        date(year, month, 1),
        date(year, month, calendar.monthrange(year, month)[1])
    ))

    for nombre, g in df.groupby("nombre"):
        mapa = g.groupby("fecha")["horas"].sum().to_dict()
        dias_laborables = [d for d in dias_mes if d.weekday() < 5 and d not in festivos_objetivos]

        objetivo = len(dias_laborables) * HORAS_LABORALES_DIA
        total = sum(mapa.values())
        diferencia = total - objetivo
        horas_extra = max(0, diferencia)
        dias_sin = [d for d in dias_laborables if d not in mapa]

        resumen.append({
            "Empleado": nombre,
            "Horas Totales": total,
            "Objetivo Mes": objetivo,
            "Diferencia": diferencia,
            "Horas Extra": horas_extra,
            "Dias Sin Fichaje": len(dias_sin)
        })

    # -----------------------------
    # PDF GLOBAL (CON EJERCICIO)
    # -----------------------------
    def generar_pdf_global(resumen):
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=A4)
        styles = getSampleStyleSheet()
        elems = []

        elems.append(Paragraph(
            f"<b>Resumen Global de Asistencia — {month_name} {year}</b><br/>"
            f"<font size=10>Ejercicio {year}</font>",
            styles["Title"]
        ))
        elems.append(Spacer(1, 12))

        data = [["Empleado","Horas","Objetivo","Días sin fichar"]]
        for r in resumen:
            data.append([
                r["Empleado"],
                hours_to_hhmm(r["Horas Totales"]),
                hours_to_hhmm(r["Objetivo Mes"]),
                str(r["Dias Sin Fichaje"])
            ])

        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.5,colors.grey),
            ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
            ('ALIGN',(1,1),(-1,-1),'CENTER')
        ]))
        elems.append(t)

        doc.build(elems)
        bio.seek(0)
        return bio

    pdf = generar_pdf_global(resumen)

    st.download_button(
        "📘 Descargar Resumen Global (PDF)",
        data=pdf.getvalue(),
        file_name=f"Resumen_Asistencia_{month_name}_{year}_Ejercicio_{year}.pdf",
        mime="application/pdf"
    )

    st.success("✅ Proceso completado correctamente.")


