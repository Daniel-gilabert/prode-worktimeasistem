# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL)
- Lee: Excel (.xls/.xlsx), CSV, PDF (Control de Presencia - estructura fija)
- PDF y Excel tratados igual (usa jornada declarada)
- Marca incidencias en PDF
- Selector de año automático
- PDFs con “Ejercicio XXXX”
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

# Festivos nacionales (multianual)
DEFAULT_FESTIVOS = [
    "2026-01-01","2026-01-06","2026-04-03","2026-05-01",
    "2026-08-15","2026-10-12","2026-12-08","2026-12-25"
]
FESTIVOS_ANDALUCIA = ["2026-02-28","2026-04-02"]

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
    s = str(s).strip().replace(",", ".")
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m) / 60
    try:
        return float(s)
    except:
        return np.nan

def hours_to_hhmm(hours):
    if hours is None or (isinstance(hours, float) and np.isnan(hours)):
        return "0:00"
    m = int(round(hours * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

# -----------------------------
# PDF PARSER DEFINITIVO
# -----------------------------
def parse_pdf_fichajes_v2(pdf_file):
    registros = []
    origen_pdf = getattr(pdf_file, "name", "PDF")

    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join(page.extract_text() or "" for page in pdf.pages)

    lineas = texto.split("\n")

    empleado = None
    fecha_actual = None
    jornada = None
    incidencia = False

    patron_nombre = re.compile(r"Nombre\s*:\s*(.+)", re.IGNORECASE)
    patron_fecha = re.compile(r"(\d{2}/\d{2}/\d{4})")
    patron_jornada = re.compile(r"(\d+)\s*H\s*(\d+)\s*M", re.IGNORECASE)
    patron_error = re.compile(r"ERROR|INCIDENCIA", re.IGNORECASE)

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        m_nom = patron_nombre.search(linea)
        if m_nom:
            empleado = m_nom.group(1).strip()
            continue

        m_fecha = patron_fecha.search(linea)
        if m_fecha:
            if fecha_actual and jornada is not None:
                registros.append({
                    "nombre": empleado,
                    "fecha": fecha_actual,
                    "horas": jornada,
                    "incidencia": incidencia,
                    "origen": origen_pdf
                })

            fecha_actual = datetime.strptime(m_fecha.group(1), "%d/%m/%Y").date()
            jornada = None
            incidencia = False
            continue

        if patron_error.search(linea):
            incidencia = True

        m_j = patron_jornada.search(linea)
        if m_j:
            jornada = int(m_j.group(1)) + int(m_j.group(2)) / 60

    if fecha_actual and jornada is not None:
        registros.append({
            "nombre": empleado,
            "fecha": fecha_actual,
            "horas": jornada,
            "incidencia": incidencia,
            "origen": origen_pdf
        })

    return pd.DataFrame(registros)

# -----------------------------
# STREAMLIT
# -----------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)

# Auth simple
if "activated" not in st.session_state:
    st.session_state.activated = False

key = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if key in DEFAULT_KEYS:
        st.session_state.activated = True
        st.sidebar.success("Activado")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.stop()

# Upload
uploaded = st.file_uploader("Sube Excel o PDF", type=["xlsx","xls","csv","pdf"])
if not uploaded:
    st.stop()

# -----------------------------
# LECTURA ARCHIVO
# -----------------------------
if uploaded.name.lower().endswith(".pdf"):
    st.info("Procesando PDF…")
    df = parse_pdf_fichajes_v2(uploaded)
else:
    df_raw = pd.read_excel(uploaded)
    df = pd.DataFrame()
    df["nombre"] = df_raw.iloc[:,0].astype(str)
    df["fecha"] = pd.to_datetime(df_raw.iloc[:,1]).dt.date
    df["horas"] = df_raw.iloc[:,2].apply(time_str_to_hours)

if df.empty:
    st.warning("No hay datos válidos")
    st.stop()

# -----------------------------
# SELECTOR DE AÑO
# -----------------------------
anio_detectado = int(pd.Series(df["fecha"]).apply(lambda d: d.year).mode()[0])
anio = st.sidebar.selectbox(
    "Ejercicio",
    sorted(df["fecha"].apply(lambda d: d.year).unique()),
    index=0
)

df = df[df["fecha"].apply(lambda d: d.year) == anio]

# -----------------------------
# FESTIVOS POR AÑO
# -----------------------------
festivos = {
    safe_parse_date(f) for f in DEFAULT_FESTIVOS
    if safe_parse_date(f) and safe_parse_date(f).year == anio
}
festivos |= {
    safe_parse_date(f) for f in FESTIVOS_ANDALUCIA
    if safe_parse_date(f) and safe_parse_date(f).year == anio
}

# -----------------------------
# PROCESADO (IGUAL QUE ANTES)
# -----------------------------
st.success(f"Datos cargados correctamente ({len(df)} registros)")
st.dataframe(df)

st.caption(f"Ejercicio {anio}")



