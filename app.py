# =========================================================
# PRODE WorkTimeAsistem - APP FINAL ESTABLE
# =========================================================

import io
import re
import zipfile
import calendar
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

# =========================================================
# CONFIG
# =========================================================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"
LOGO_FILENAME = "logo-prode.jpg"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7

DEFAULT_KEYS = [
    ADMIN_KEY,
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

# Colores
COLOR_OK = "#e6ffef"
COLOR_WARN = "#fff3cd"
COLOR_BAD = "#f8d7da"
COLOR_EXTRA = "#d8fcd8"
COLOR_DEFICIT = "#ffe4b2"
COLOR_FESTIVO = "#cfe3ff"
COLOR_VACACIONES = "#e4ceff"
COLOR_PERMISO = "#ffd6f3"
COLOR_BAJA = "#c9f2e7"

# =========================================================
# SESSION STATE SAFE INIT (CLAVE PARA QUE NO PETE)
# =========================================================
if "user_keys" not in st.session_state:
    st.session_state.user_keys = DEFAULT_KEYS.copy()
if "active" not in st.session_state:
    st.session_state.active = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "ausencias" not in st.session_state:
    st.session_state.ausencias = {}
if "festivos_locales_globales" not in st.session_state:
    st.session_state.festivos_locales_globales = set()
if "festivos_locales_por_empleado" not in st.session_state:
    st.session_state.festivos_locales_por_empleado = {}

# =========================================================
# HELPERS
# =========================================================
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
    if "H" in s.upper():
        h = re.findall(r"(\d+)H", s.upper())
        m = re.findall(r"(\d+)M", s.upper())
        return (int(h[0]) if h else 0) + (int(m[0]) if m else 0)/60
    return float(s.replace(",", "."))

def hours_to_hhmm(h):
    if h is None or np.isnan(h):
        return "0:00"
    m = int(round(h*60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end-start).days+1):
        yield start + timedelta(n)

# =========================================================
# FESTIVOS AUTOMÁTICOS (AÑO EN CURSO)
# =========================================================
def festivos_nacionales_y_andalucia(year):
    base = [
        date(year,1,1), date(year,1,6), date(year,5,1),
        date(year,8,15), date(year,10,12),
        date(year,11,1), date(year,12,6), date(year,12,8), date(year,12,25),
        date(year,2,28)  # Andalucía
    ]
    return set(base)

# =========================================================
# PDF PARSER
# =========================================================
def parse_pdf_fichajes(uploaded_pdf):
    registros = []
    empleado = None
    patron = re.compile(r"(\d{2}-\w{3}\.-\d{2}).*?([\dHMS\s]+)$")

    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                if line.startswith("Nombre:"):
                    empleado = line.replace("Nombre:", "").strip()
                m = patron.search(line)
                if m and empleado:
                    fecha_raw, jornada = m.groups()
                    fecha = pd.to_datetime(fecha_raw, dayfirst=True, errors="coerce")
                    if pd.isna(fecha):
                        continue
                    h = re.findall(r"(\d+)H", jornada)
                    m2 = re.findall(r"(\d+)M", jornada)
                    horas = (int(h[0]) if h else 0) + (int(m2[0]) if m2 else 0)/60
                    registros.append({
                        "nombre": empleado,
                        "fecha": fecha.date(),
                        "horas": horas
                    })
    return pd.DataFrame(registros)

# =========================================================
# UI
# =========================================================
st.set_page_config(APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

with st.expander("📘 Cómo funciona esta herramienta"):
    st.markdown("""
- Subes **PDF, Excel o CSV** de fichajes  
- Se aplican **festivos nacionales y de Andalucía automáticamente**  
- Puedes añadir **festivos locales** (globales o por empleado)  
- Vacaciones, permisos y bajas **no cuentan como sin fichar**  
- Generas **informes individuales + resumen global + ZIP**
""")

# =========================================================
# LOGIN
# =========================================================
st.sidebar.header("🔐 Acceso")
key = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if key in st.session_state.user_keys:
        st.session_state.active = True
        st.session_state.is_admin = (key == ADMIN_KEY)
        st.sidebar.success("Acceso correcto")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.active:
    st.stop()

# =========================================================
# ADMIN KEYS
# =========================================================
if st.session_state.is_admin:
    st.sidebar.subheader("🛠 Gestión de claves")
    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir"):
        if nueva and nueva not in st.session_state.user_keys:
            st.session_state.user_keys.append(nueva)
    borrar = st.sidebar.selectbox("Eliminar clave", [k for k in st.session_state.user_keys if k != ADMIN_KEY])
    if st.sidebar.button("Eliminar"):
        st.session_state.user_keys.remove(borrar)

# =========================================================
# UPLOAD
# =========================================================
uploaded = st.file_uploader("📂 Subir fichero", type=["pdf","xlsx","xls","csv"])
if not uploaded:
    st.stop()

with st.spinner("⏳ Procesando fichero…"):
    if uploaded.name.lower().endswith(".pdf"):
        df = parse_pdf_fichajes(uploaded)
    else:
        df_raw = pd.read_excel(uploaded) if uploaded.name.endswith(("xls","xlsx")) else pd.read_csv(uploaded)
        df = pd.DataFrame()
        df["nombre"] = df_raw.iloc[:,0].astype(str)
        df["fecha"] = pd.to_datetime(df_raw.iloc[:,1]).dt.date
        df["horas"] = df_raw.iloc[:,2].apply(time_str_to_hours)

st.success(f"Registros cargados: {len(df)}")

# =========================================================
# DETECT MONTH
# =========================================================
month = df["fecha"].iloc[0].month
year = df["fecha"].iloc[0].year
dias_mes = list(daterange(date(year,month,1), date(year,month,calendar.monthrange(year,month)[1])))
festivos_auto = festivos_nacionales_y_andalucia(year)

# =========================================================
# PROCESAR
# =========================================================
if st.button("⚙️ Procesar datos y generar informes"):
    with st.spinner("📄 Generando informes PDF…"):
        resumen = []
        zip_buffer = io.BytesIO()
        zipf = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED)

        for emp, g in df.groupby("nombre"):
            mapa = g.groupby("fecha")["horas"].sum().to_dict()
            dias_no = festivos_auto | st.session_state.festivos_locales_globales | set(st.session_state.festivos_locales_por_empleado.get(emp, []))
            dias_lab = [d for d in dias_mes if d.weekday()<5 and d not in dias_no]
            objetivo = len(dias_lab) * HORAS_LABORALES_DIA
            total = sum(mapa.values())
            sin = len([d for d in dias_lab if mapa.get(d,0)==0])

            resumen.append((emp,total,objetivo,sin))

            # PDF individual (simple y limpio)
            bio = io.BytesIO()
            doc = SimpleDocTemplate(bio, pagesize=A4)
            elems = [Paragraph(f"<b>{emp} — {month}/{year}</b>", getSampleStyleSheet()["Title"])]
            elems.append(Spacer(1,12))
            t = Table([["Total",hours_to_hhmm(total)],["Objetivo",hours_to_hhmm(objetivo)],["Sin fichar",sin]])
            t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey)]))
            elems.append(t)
            doc.build(elems)
            zipf.writestr(f"{emp}.pdf", bio.getvalue())
            st.download_button(f"📄 {emp}", bio.getvalue(), f"{emp}.pdf")

        # Resumen global
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=landscape(A4))
        data = [["Empleado","Horas","Objetivo","Sin fichar"]] + [[r[0],hours_to_hhmm(r[1]),hours_to_hhmm(r[2]),r[3]] for r in resumen]
        table = Table(data)
        table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey)]))
        doc.build([table])
        zipf.writestr("Resumen_Global.pdf", bio.getvalue())
        zipf.close()

        st.download_button("📦 Descargar ZIP completo", zip_buffer.getvalue(), "Informes_PRODE.zip")

st.success("Proceso completado")



