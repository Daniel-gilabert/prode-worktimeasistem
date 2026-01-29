# =========================================================
# PRODE WorkTimeAsistem - FINAL DEFINITIVO (EXCEL REAL)
# =========================================================

import os, io, calendar, re, zipfile
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
HORAS_DIA = HORAS_SEMANALES / 5  # 7.7

BASE_DIR = Path(__file__).parent.resolve()
OUT_DIR = BASE_DIR / "informes"
OUT_DIR.mkdir(exist_ok=True)

# =========================================================
# SESSION STATE SEGURO
# =========================================================
def init_state():
    defaults = {
        "activated": False,
        "is_admin": False,
        "user_keys": [
            ADMIN_KEY,
            "PRODE-ULTIMAMILLA-DGC",
            "PRODE-ULTIMAMILLA-JLM",
            "PRODE-CAPITALHUMANO-ZMGR"
        ],
        "ausencias": {}
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
    for n in range((end-start).days+1):
        yield start + timedelta(days=n)

# =========================================================
# UI
# =========================================================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

with st.expander("ℹ️ Cómo funciona esta herramienta"):
    st.markdown("""
- Subes **Excel REAL de fichajes**
- El Excel debe tener:
  - Empleado / Nombre
  - Fecha
  - Hora Entrada
  - Hora Salida
- Las horas se **calculan automáticamente**
- Se generan informes individuales y un resumen global
""")

# =========================================================
# LOGIN
# =========================================================
st.sidebar.header("🔐 Acceso")
key = st.sidebar.text_input("Clave", type="password")

if st.sidebar.button("Activar"):
    if key in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.is_admin = (key == ADMIN_KEY)
        st.sidebar.success("Acceso concedido")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.stop()

# =========================================================
# UPLOAD EXCEL
# =========================================================
st.subheader("📂 Subir Excel de fichajes")
uploaded = st.file_uploader("Excel (.xlsx)", type=["xlsx"])

if not uploaded:
    st.stop()

df_raw = pd.read_excel(uploaded)

# =========================================================
# DETECTAR COLUMNAS
# =========================================================
cols = {c.lower(): c for c in df_raw.columns}

def find_col(keys):
    for k in keys:
        for c in cols:
            if k in c:
                return cols[c]
    return None

col_nombre  = find_col(["empleado","nombre"])
col_fecha   = find_col(["fecha"])
col_in      = find_col(["entrada","hora entrada"])
col_out     = find_col(["salida","hora salida"])

if not all([col_nombre, col_fecha, col_in, col_out]):
    st.error("❌ El Excel debe tener columnas: Empleado, Fecha, Entrada, Salida")
    st.write(df_raw.columns.tolist())
    st.stop()

# =========================================================
# NORMALIZAR Y CALCULAR HORAS
# =========================================================
df = pd.DataFrame()
df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce").dt.date
df["entrada"] = pd.to_datetime(df_raw[col_in], errors="coerce")
df["salida"] = pd.to_datetime(df_raw[col_out], errors="coerce")

df = df.dropna(subset=["nombre","fecha"])

def calc_hours(row):
    if pd.isna(row["entrada"]) or pd.isna(row["salida"]):
        return 0.0
    delta = row["salida"] - row["entrada"]
    return round(delta.total_seconds()/3600,2)

df["horas"] = df.apply(calc_hours, axis=1)
df = df[["nombre","fecha","horas"]]

st.success(f"✅ Registros cargados: {len(df)}")
st.dataframe(df.head(20))

# =========================================================
# PROCESAR
# =========================================================
if st.button("⚙️ Procesar datos"):
    with st.spinner("⏳ Generando informes…"):
        resumen = df.groupby("nombre")["horas"].sum().reset_index()

    st.subheader("📊 Resumen Global")
    for _, r in resumen.iterrows():
        st.markdown(
            f"<div style='padding:6px;background:#eef;border-radius:6px;margin-bottom:4px;'>"
            f"<b>{r['nombre']}</b> — {hours_to_hhmm(r['horas'])} h"
            f"</div>",
            unsafe_allow_html=True
        )

    # ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer,"w") as z:
        for _, r in resumen.iterrows():
            z.writestr(
                f"{r['nombre'].replace(' ','_')}.txt",
                f"{r['nombre']} — Total horas: {hours_to_hhmm(r['horas'])}"
            )

    st.download_button(
        "📦 Descargar informes (ZIP)",
        zip_buffer.getvalue(),
        file_name="Informes_PRODE.zip",
        mime="application/zip"
    )

st.write("🟢 Aplicación estable y cerrada.")








