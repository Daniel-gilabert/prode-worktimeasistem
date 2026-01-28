# =========================================================
# PRODE WorkTimeAsistem - APP FINAL DEFINITIVA
# =========================================================

import io
import re
import zipfile
import calendar
from datetime import datetime, timedelta, date
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

# =========================================================
# CONFIG
# =========================================================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7

DEFAULT_KEYS = [
    ADMIN_KEY,
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

# =========================================================
# SESSION STATE SAFE INIT
# =========================================================
def init_state():
    defaults = {
        "user_keys": DEFAULT_KEYS.copy(),
        "active": False,
        "is_admin": False,
        "ausencias": {},
        "festivos_locales_globales": set(),
        "festivos_locales_por_empleado": {}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# =========================================================
# HELPERS
# =========================================================
def hours_to_hhmm(h):
    if h is None or np.isnan(h):
        return "0:00"
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

def festivos_auto(year):
    return {
        date(year,1,1), date(year,1,6), date(year,2,28),
        date(year,5,1), date(year,8,15),
        date(year,10,12), date(year,11,1),
        date(year,12,6), date(year,12,8), date(year,12,25)
    }

# =========================================================
# PDF PARSER PRODE (ROBUSTO)
# =========================================================
def parse_pdf_prode(uploaded_pdf):
    registros = []
    empleado = None

    patron_fecha = re.compile(r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{2}-\w{3}\.-\d{2})")
    patron_horas = re.compile(r"(\d+)\s*H|\d+:\d{2}")

    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                if "Nombre" in line:
                    empleado = line.split(":")[-1].strip()

                if empleado:
                    f = patron_fecha.search(line)
                    if not f:
                        continue

                    fecha = pd.to_datetime(f.group(), dayfirst=True, errors="coerce")
                    if pd.isna(fecha):
                        continue

                    h = re.findall(r"(\d+)H", line.upper())
                    m = re.findall(r"(\d+)M", line.upper())
                    horas = (int(h[0]) if h else 0) + (int(m[0]) if m else 0)/60

                    if horas > 0:
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
- Subes **PDF, Excel o CSV**
- Se aplican **festivos nacionales + Andalucía**
- Festivos locales por empleado o globales
- Vacaciones, permisos y bajas **no cuentan**
- Generas PDFs individuales, resumen y ZIP
""")

# =========================================================
# LOGIN
# =========================================================
st.sidebar.header("🔐 Acceso")
clave = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if clave in st.session_state.user_keys:
        st.session_state.active = True
        st.session_state.is_admin = (clave == ADMIN_KEY)
        st.sidebar.success("Acceso concedido")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.active:
    st.stop()

# =========================================================
# ADMIN
# =========================================================
if st.session_state.is_admin:
    st.sidebar.subheader("🛠 Gestión de claves")
    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir clave"):
        if nueva and nueva not in st.session_state.user_keys:
            st.session_state.user_keys.append(nueva)

    borrar = st.sidebar.selectbox(
        "Eliminar clave",
        [k for k in st.session_state.user_keys if k != ADMIN_KEY]
    )
    if st.sidebar.button("Eliminar clave"):
        st.session_state.user_keys.remove(borrar)

# =========================================================
# UPLOAD
# =========================================================
uploaded = st.file_uploader("📂 Subir fichero", type=["pdf","xlsx","xls","csv"])
if not uploaded:
    st.stop()

with st.spinner("⏳ Leyendo fichero…"):
    if uploaded.name.lower().endswith(".pdf"):
        df = parse_pdf_prode(uploaded)
    else:
        df_raw = pd.read_excel(uploaded) if uploaded.name.endswith(("xls","xlsx")) else pd.read_csv(uploaded)
        df = pd.DataFrame({
            "nombre": df_raw.iloc[:,0].astype(str),
            "fecha": pd.to_datetime(df_raw.iloc[:,1], errors="coerce").dt.date,
            "horas": df_raw.iloc[:,2]
        })

# =========================================================
# VALIDACIÓN CRÍTICA
# =========================================================
if df.empty:
    st.error(
        "❌ No se han encontrado registros válidos.\n\n"
        "Este PDF no contiene fichajes diarios reconocibles."
    )
    st.stop()

st.success(f"Registros cargados: {len(df)}")

# =========================================================
# DETECTAR MES
# =========================================================
month = df["fecha"].iloc[0].month
year = df["fecha"].iloc[0].year
dias_mes = list(daterange(date(year,month,1), date(year,month,calendar.monthrange(year,month)[1])))
festivos = festivos_auto(year)

# =========================================================
# PROCESAR
# =========================================================
if st.button("⚙️ Procesar y generar informes"):
    with st.spinner("📄 Generando informes…"):
        resumen = []
        zip_buffer = io.BytesIO()
        zipf = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED)

        for emp, g in df.groupby("nombre"):
            mapa = g.groupby("fecha")["horas"].sum().to_dict()
            dias_lab = [d for d in dias_mes if d.weekday()<5 and d not in festivos]
            objetivo = len(dias_lab) * HORAS_LABORALES_DIA
            total = sum(mapa.values())
            sin = len([d for d in dias_lab if mapa.get(d,0)==0])

            resumen.append([emp, hours_to_hhmm(total), hours_to_hhmm(objetivo), sin])

            bio = io.BytesIO()
            doc = SimpleDocTemplate(bio, pagesize=A4)
            elems = [
                Paragraph(f"<b>{emp} — {month}/{year}</b>", getSampleStyleSheet()["Title"]),
                Spacer(1,12),
                Table(
                    [["Total",hours_to_hhmm(total)],["Objetivo",hours_to_hhmm(objetivo)],["Sin fichar",sin]],
                    style=[('GRID',(0,0),(-1,-1),0.5,colors.grey)]
                )
            ]
            doc.build(elems)
            zipf.writestr(f"{emp}.pdf", bio.getvalue())
            st.download_button(f"📄 {emp}", bio.getvalue(), f"{emp}.pdf")

        # Resumen global
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=landscape(A4))
        table = Table([["Empleado","Horas","Objetivo","Sin fichar"]] + resumen,
                      style=[('GRID',(0,0),(-1,-1),0.5,colors.grey)])
        doc.build([table])
        zipf.writestr("Resumen_Global.pdf", bio.getvalue())
        zipf.close()

        st.download_button("📦 Descargar ZIP completo", zip_buffer.getvalue(), "Informes_PRODE.zip")

st.success("Proceso finalizado correctamente")




