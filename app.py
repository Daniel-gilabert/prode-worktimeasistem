# app.py
"""
PRODE WorkTimeAsistem
- Analiza Excel / CSV / PDF (misma lógica)
- PDF tratado igual que Excel usando la JORNADA declarada
- Marca incidencias (ERROR, incoherencias)
- Selector automático de año
- Base auditable (NO registra fichajes, solo analiza)
"""

import io
import re
import calendar
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =============================
# CONFIG
# =============================
APP_NAME = "PRODE WorkTimeAsistem"
HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

CLAVES_VALIDAS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

# Festivos 2026
DEFAULT_FESTIVOS = [
    "2026-01-01","2026-01-06","2026-04-03","2026-05-01",
    "2026-08-15","2026-10-12","2026-12-08","2026-12-25"
]
FESTIVOS_ANDALUCIA = ["2026-02-28","2026-04-02"]

# =============================
# HELPERS
# =============================
def safe_parse_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def hours_to_hhmm(h):
    if h is None or pd.isna(h):
        return "0:00"
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

# =============================
# PDF PARSER REAL (V3)
# =============================
def parse_pdf_fichajes_v3(pdf_file):
    """
    Parser cerrado para el PDF REAL de Control de Presencia PRODE
    Usa la JORNADA declarada (NO reconstruye horas)
    """

    registros = []
    origen_pdf = getattr(pdf_file, "name", "PDF")

    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join(page.extract_text() or "" for page in pdf.pages)

    empleado = None

    patron_nombre = re.compile(r"Nombre:\s*(.+)", re.IGNORECASE)
    patron_linea = re.compile(
        r"(\d{2}-[a-z]{3}\.-\d{2})\s+"
        r"(\d{1,2}:\d{2})\s+"
        r"(\d{1,2}:\d{2})?\s*"
        r"(\d+H\s*\d+M\s*\d+S)",
        re.IGNORECASE
    )

    for linea in texto.split("\n"):
        linea = linea.strip()

        m_nom = patron_nombre.search(linea)
        if m_nom:
            empleado = m_nom.group(1).strip()
            continue

        m = patron_linea.search(linea)
        if not m or not empleado:
            continue

        fecha_raw, _, _, jornada_raw = m.groups()

        try:
            fecha = datetime.strptime(fecha_raw, "%d-%b.-%y").date()
        except:
            continue

        incidencia = "ERROR" in linea.upper()

        h = re.search(r"(\d+)H", jornada_raw)
        m_ = re.search(r"(\d+)M", jornada_raw)
        s = re.search(r"(\d+)S", jornada_raw)

        horas = (
            (int(h.group(1)) if h else 0) +
            (int(m_.group(1)) if m_ else 0) / 60 +
            (int(s.group(1)) if s else 0) / 3600
        )

        registros.append({
            "nombre": empleado,
            "fecha": fecha,
            "horas": round(horas, 2),
            "incidencia": incidencia,
            "origen": origen_pdf
        })

    return pd.DataFrame(registros)

# =============================
# STREAMLIT UI
# =============================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)

# --- AUTH ---
if "auth" not in st.session_state:
    st.session_state.auth = False

clave = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if clave in CLAVES_VALIDAS:
        st.session_state.auth = True
        st.sidebar.success("Acceso concedido")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.auth:
    st.stop()

# --- UPLOAD ---
uploaded = st.file_uploader("Sube Excel o PDF", type=["xlsx","xls","csv","pdf"])
if not uploaded:
    st.stop()

# =============================
# LECTURA ARCHIVO
# =============================
if uploaded.name.lower().endswith(".pdf"):
    st.info("Procesando PDF…")
    df = parse_pdf_fichajes_v3(uploaded)
else:
    df_raw = pd.read_excel(uploaded)
    df = pd.DataFrame()
    df["nombre"] = df_raw.iloc[:,0].astype(str)
    df["fecha"] = pd.to_datetime(df_raw.iloc[:,1]).dt.date
    df["horas"] = df_raw.iloc[:,2]
    df["incidencia"] = False
    df["origen"] = uploaded.name

if df.empty:
    st.warning("No hay datos válidos")
    st.stop()

# =============================
# SELECTOR DE AÑO
# =============================
anio_detectado = int(df["fecha"].apply(lambda d: d.year).mode()[0])
anio = st.sidebar.selectbox(
    "Ejercicio",
    sorted(df["fecha"].apply(lambda d: d.year).unique()),
    index=0
)

df = df[df["fecha"].apply(lambda d: d.year) == anio]

# =============================
# FESTIVOS
# =============================
festivos = {
    safe_parse_date(f) for f in DEFAULT_FESTIVOS
    if safe_parse_date(f) and safe_parse_date(f).year == anio
}
festivos |= {
    safe_parse_date(f) for f in FESTIVOS_ANDALUCIA
    if safe_parse_date(f) and safe_parse_date(f).year == anio
}

# =============================
# PROCESADO
# =============================
st.success(f"{len(df)} jornadas cargadas · Ejercicio {anio}")
st.dataframe(df)

# =============================
# RESUMEN POR EMPLEADO
# =============================
st.subheader("Resumen por empleado")

for nombre, g in df.groupby("nombre"):
    dias_mes = list(daterange(
        date(anio, g["fecha"].min().month, 1),
        date(anio, g["fecha"].min().month,
             calendar.monthrange(anio, g["fecha"].min().month)[1])
    ))

    dias_laborables = [
        d for d in dias_mes
        if d.weekday() < 5 and d not in festivos
    ]

    objetivo = len(dias_laborables) * HORAS_LABORALES_DIA
    total = g["horas"].sum()
    diferencia = total - objetivo

    st.markdown(
        f"**{nombre}** — "
        f"Total: {hours_to_hhmm(total)} | "
        f"Objetivo: {hours_to_hhmm(objetivo)} | "
        f"Diferencia: {hours_to_hhmm(diferencia)}"
    )

st.caption("PRODE WorkTimeAsistem · Analizador auditable · NO registra fichajes")





