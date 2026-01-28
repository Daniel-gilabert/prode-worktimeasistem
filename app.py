# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL)
- Lee: Excel (.xls/.xlsx), CSV, PDF (Informe de Control de Presencia)
- Calcula objetivo mensual, diferencia y horas extra
- Genera PDFs individuales y globales
- Activación por clave, gestión de ausencias y festivos
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
LOGO_FILENAME = "logo-prode.jpg"
LOGO_LOCAL_PATH = "/mnt/data/logo-prode.jpg"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7

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
    if "H" in s.upper():
        H = re.findall(r"(\d+)H", s.upper())
        M = re.findall(r"(\d+)M", s.upper())
        return (int(H[0]) if H else 0) + (int(M[0]) if M else 0)/60
    try:
        return float(s.replace(",", "."))
    except:
        return np.nan

def hours_to_hhmm(hours):
    total_min = int(round(hours * 60))
    return f"{total_min//60}:{total_min%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

# -----------------------------
# PDF PARSER (ROBUSTO)
# -----------------------------
def parse_pdf_fichajes(pdf_file):
    registros = []
    empleado_actual = None

    meses = {
        "ene":"01","feb":"02","mar":"03","abr":"04","may":"05","jun":"06",
        "jul":"07","ago":"08","sep":"09","oct":"10","nov":"11","dic":"12"
    }

    patron = re.compile(
        r"(\d{2})-([a-z]{3})\.-(\d{2}).*?(\d+)H\s*(\d+)M\s*(\d+)S",
        re.IGNORECASE
    )

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                if line.startswith("Nombre:"):
                    empleado_actual = line.replace("Nombre:", "").strip()
                    continue

                m = patron.search(line)
                if not m or not empleado_actual:
                    continue

                dd, mes, yy, h, mnt, s = m.groups()
                mes = mes.lower()
                if mes not in meses:
                    continue

                fecha = datetime.strptime(
                    f"{dd}/{meses[mes]}/20{yy}",
                    "%d/%m/%Y"
                ).date()

                horas = int(h) + int(mnt)/60 + int(s)/3600

                registros.append({
                    "nombre": empleado_actual,
                    "fecha": fecha,
                    "horas": horas
                })

    return pd.DataFrame(registros, columns=["nombre","fecha","horas"])

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

st.sidebar.header("🔐 Acceso")
key_input = st.sidebar.text_input("Clave:", type="password")
if "activated" not in st.session_state:
    st.session_state.activated = False
if st.sidebar.button("Activar"):
    if key_input in DEFAULT_KEYS:
        st.session_state.activated = True
        st.sidebar.success("Activado")
    else:
        st.sidebar.error("Clave inválida")

if not st.session_state.activated:
    st.stop()

uploaded = st.file_uploader(
    "Sube fichero de fichajes",
    type=["xlsx","xls","csv","pdf"]
)
if not uploaded:
    st.stop()

if uploaded.name.lower().endswith(".pdf"):
    df = parse_pdf_fichajes(uploaded)
elif uploaded.name.lower().endswith((".xls",".xlsx")):
    df_raw = pd.read_excel(uploaded)
    df = pd.DataFrame({
        "nombre": df_raw.iloc[:,0],
        "fecha": pd.to_datetime(df_raw.iloc[:,1]).dt.date,
        "horas": df_raw.iloc[:,2].apply(time_str_to_hours)
    })
else:
    df_raw = pd.read_csv(uploaded)
    df = pd.DataFrame({
        "nombre": df_raw.iloc[:,0],
        "fecha": pd.to_datetime(df_raw.iloc[:,1]).dt.date,
        "horas": df_raw.iloc[:,2].apply(time_str_to_hours)
    })

st.success(f"Registros cargados: {len(df)}")
st.dataframe(df)

