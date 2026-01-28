# app.py — PRODE WorkTimeAsistem (FINAL + UX)

import io, re, calendar
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =====================================================
# CONFIG
# =====================================================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

DEFAULT_KEYS = [
    ADMIN_KEY,
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

INFORMES_DIR = Path("informes")
INFORMES_DIR.mkdir(exist_ok=True)

# =====================================================
# HELPERS
# =====================================================
def safe_parse_date(x):
    try: return pd.to_datetime(x).date()
    except: return None

def hours_to_hhmm(h):
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

# =====================================================
# PDF PARSER
# =====================================================
def parse_pdf_fichajes(pdf):
    meses = {
        "ene":"01","feb":"02","mar":"03","abr":"04","may":"05","jun":"06",
        "jul":"07","ago":"08","sep":"09","oct":"10","nov":"11","dic":"12"
    }
    patron = re.compile(
        r"(\d{2})-([a-z]{3})\.-(\d{2}).*?(\d+)H\s*(\d+)M\s*(\d+)S",
        re.I
    )
    rows, emp = [], None

    with pdfplumber.open(pdf) as p:
        for page in p.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split("\n"):
                if line.startswith("Nombre:"):
                    emp = line.replace("Nombre:", "").strip()
                m = patron.search(line)
                if m and emp:
                    d, mes, y, h, mi, s = m.groups()
                    fecha = datetime.strptime(
                        f"{d}/{meses[mes.lower()]}/20{y}",
                        "%d/%m/%Y"
                    ).date()
                    horas = int(h) + int(mi)/60 + int(s)/3600
                    rows.append({"nombre": emp, "fecha": fecha, "horas": horas})

    return pd.DataFrame(rows)

# =====================================================
# UI
# =====================================================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

# ---------------- SESSION ----------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.user_keys = DEFAULT_KEYS.copy()
    st.session_state.is_admin = False
    st.session_state.ausencias = {}
    st.session_state.festivos_personales = {}

# ---------------- LOGIN ----------------
st.sidebar.header("🔐 Acceso")
clave = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if clave in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.is_admin = (clave == ADMIN_KEY)
        st.sidebar.success("Acceso concedido")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.stop()

# ---------------- ADMIN ----------------
if st.session_state.is_admin:
    st.sidebar.subheader("🛠 Administración")
    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir clave"):
        if nueva and nueva not in st.session_state.user_keys:
            st.session_state.user_keys.append(nueva)
            st.sidebar.success("Clave añadida")

# ---------------- UPLOAD ----------------
uploaded = st.file_uploader(
    "Sube fichero de fichajes (PDF / Excel / CSV)",
    type=["pdf","xlsx","xls","csv"]
)
if not uploaded:
    st.stop()

if uploaded.name.lower().endswith(".pdf"):
    df = parse_pdf_fichajes(uploaded)
elif uploaded.name.lower().endswith((".xls",".xlsx")):
    df = pd.read_excel(uploaded)
    df.columns = ["nombre","fecha","horas"]
else:
    df = pd.read_csv(uploaded)
    df.columns = ["nombre","fecha","horas"]

df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
st.success(f"Registros cargados: {len(df)}")
st.dataframe(df)

empleados = sorted(df["nombre"].unique())

# ---------------- AUSENCIAS ----------------
st.subheader("🏖️ Ausencias")
emp_sel = st.selectbox("Empleado", empleados)
motivo = st.selectbox("Motivo", ["Vacaciones","Permiso","Baja médica"])
rango = st.date_input("Rango", [])

if st.button("Añadir ausencia") and len(rango) == 2:
    st.session_state.ausencias.setdefault(emp_sel, {}) \
        .setdefault(motivo, []) \
        .extend(list(daterange(rango[0], rango[1])))
    st.success("Ausencia registrada")

# ---------------- FESTIVOS EXTRA ----------------
st.subheader("📅 Festivo extra por empleado")
emp_fest = st.selectbox("Empleado (festivo extra)", empleados, key="fest_emp")
fest_date = st.date_input("Fecha festiva")

if st.button("Añadir festivo extra"):
    st.session_state.festivos_personales.setdefault(emp_fest, []).append(fest_date)
    st.success("Festivo añadido")

# ---------------- LEYENDA ----------------
st.subheader("🎨 Leyenda de colores")
st.markdown("""
- 🟩 **Verde**: correcto (≤ 2 días sin fichar)  
- 🟨 **Amarillo**: atención (3–4 días sin fichar)  
- 🟥 **Rojo**: grave (> 4 días sin fichar)  
""")

# =====================================================
# PROCESAR
# =====================================================
if st.button("⚙️ Procesar datos y generar informes"):

    with st.spinner("Procesando datos y generando informes..."):

        festivos = {safe_parse_date(f) for f in DEFAULT_FESTIVOS}
        festivos |= {safe_parse_date(f) for f in FESTIVOS_ANDALUCIA}

        month = df["fecha"].iloc[0].month
        year = df["fecha"].iloc[0].year

        dias_mes = list(daterange(
            date(year, month, 1),
            date(year, month, calendar.monthrange(year, month)[1])
        ))

        st.subheader("📊 Resumen Global")

        for emp, g in df.groupby("nombre"):
            mapa = g.groupby("fecha")["horas"].sum().to_dict()
            aus = list(chain.from_iterable(
                st.session_state.ausencias.get(emp, {}).values()
            ))
            fest_emp = set(st.session_state.festivos_personales.get(emp, []))

            dias_no_lab = festivos | set(aus) | fest_emp
            dias_lab = [d for d in dias_mes if d.weekday() < 5 and d not in dias_no_lab]

            objetivo = len(dias_lab) * HORAS_LABORALES_DIA
            total = sum(mapa.values())
            sin = len([d for d in dias_lab if d not in mapa])

            color = "#e6ffef" if sin <= 2 else "#fff3cd" if sin <= 4 else "#f8d7da"

            st.markdown(
                f"<div style='background:{color};padding:8px;border-radius:6px'>"
                f"<b>{emp}</b> — Total {hours_to_hhmm(total)} h | "
                f"Objetivo {hours_to_hhmm(objetivo)} h | "
                f"Sin fichar {sin} días</div>",
                unsafe_allow_html=True
            )

    st.success("✅ Proceso completado")



