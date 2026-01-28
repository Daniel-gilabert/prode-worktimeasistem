# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL DEFINITIVO)
- Lee Excel, CSV y PDF (Informe Control Presencia)
- MISMO flujo que la versión original
- PDF es SOLO una fuente de datos extra
"""

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

# =============================
# CONFIG
# =============================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"
LOGO_FILENAME = "logo-prode.jpg"

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

# =============================
# HELPERS
# =============================
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

# =============================
# PDF PARSER (SOLO FUENTE)
# =============================
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

    return pd.DataFrame(registros)

# =============================
# STREAMLIT UI
# =============================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

# --- Login ---
if "activated" not in st.session_state:
    st.session_state.activated = False

st.sidebar.header("🔐 Acceso")
key_input = st.sidebar.text_input("Introduce tu clave:", type="password")
if st.sidebar.button("Activar"):
    if key_input in DEFAULT_KEYS:
        st.session_state.activated = True
        st.sidebar.success("Activado")
    else:
        st.sidebar.error("Clave inválida")

if not st.session_state.activated:
    st.stop()

# =============================
# UPLOAD
# =============================
uploaded = st.file_uploader(
    "Sube fichero de fichajes (Excel / CSV / PDF)",
    type=["xlsx","xls","csv","pdf"]
)
if not uploaded:
    st.stop()

# =============================
# READ FILE → df
# =============================
if uploaded.name.lower().endswith(".pdf"):
    df = parse_pdf_fichajes(uploaded)
elif uploaded.name.lower().endswith((".xls",".xlsx")):
    df_raw = pd.read_excel(uploaded)
    df = pd.DataFrame({
        "nombre": df_raw.iloc[:,0].astype(str).str.strip(),
        "fecha": pd.to_datetime(df_raw.iloc[:,1]).dt.date,
        "horas": df_raw.iloc[:,2].apply(time_str_to_hours)
    })
else:
    df_raw = pd.read_csv(uploaded)
    df = pd.DataFrame({
        "nombre": df_raw.iloc[:,0].astype(str).str.strip(),
        "fecha": pd.to_datetime(df_raw.iloc[:,1]).dt.date,
        "horas": df_raw.iloc[:,2].apply(time_str_to_hours)
    })

st.success(f"Registros cargados: {len(df)}")
st.dataframe(df)

if st.button("⚙️ Procesar datos y generar informes"):

    # =============================
    # PREPARAR FESTIVOS Y AUSENCIAS
    # =============================
    festivos_objetivos = {safe_parse_date(f) for f in DEFAULT_FESTIVOS if safe_parse_date(f)}
    festivos_objetivos |= {safe_parse_date(f) for f in FESTIVOS_ANDALUCIA if safe_parse_date(f)}

    dias_por_empleado = st.session_state.get("dias_por_empleado", {})

    # =============================
    # DETECTAR MES / AÑO
    # =============================
    month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
    year = int(df["fecha"].apply(lambda d: d.year).mode()[0])

    dias_mes = list(
        daterange(
            date(year, month, 1),
            date(year, month, calendar.monthrange(year, month)[1])
        )
    )

    # =============================
    # AGRUPAR POR EMPLEADO
    # =============================
    resumen_empleados = []
    for nombre, g in df.groupby("nombre"):
        mapa = {}
        s = g.groupby("fecha")["horas"].sum()
        for d, h in s.items():
            mapa[d] = float(h) if not pd.isna(h) else 0.0

        resumen_empleados.append({
            "nombre": nombre,
            "mapa_horas": mapa,
            "total_horas": s.sum()
        })

    # =============================
    # CALCULO GLOBAL
    # =============================
    global_data = []

    for r in resumen_empleados:
        nombre = r["nombre"]
        mapa = r["mapa_horas"]

        ausencias = list(
            chain.from_iterable(dias_por_empleado.get(nombre, {}).values())
        ) if dias_por_empleado.get(nombre) else []

        dias_no_laborables = set(festivos_objetivos).union(set(ausencias))
        dias_laborables = [
            d for d in dias_mes if d.weekday() < 5 and d not in dias_no_laborables
        ]

        objetivo_mes = len(dias_laborables) * HORAS_LABORALES_DIA
        horas_totales = r["total_horas"]
        diferencia = horas_totales - objetivo_mes
        horas_extra = max(0, diferencia)

        dias_con = len([
            d for d in dias_laborables
            if d in mapa and mapa.get(d, 0) > 0
        ])

        dias_sin_list = [
            d for d in dias_laborables
            if d not in mapa or mapa.get(d, 0) == 0
        ]

        global_data.append({
            "Empleado": nombre,
            "Horas Totales": horas_totales,
            "Objetivo Mes": objetivo_mes,
            "Diferencia": diferencia,
            "Horas Extra": horas_extra,
            "Dias Con Fichaje": dias_con,
            "Dias Sin Fichaje": len(dias_sin_list),
            "Fechas Sin Fichar": dias_sin_list,
            "mapa_horas": mapa,
            "Ausencias": ausencias
        })

    # =============================
    # MOSTRAR RESUMEN EN PANTALLA
    # =============================
    st.subheader("📊 Resumen Global")

    for r in global_data:
        if r["Dias Sin Fichaje"] > 4:
            color = "#f8d7da"
        elif r["Dias Sin Fichaje"] > 2:
            color = "#fff3cd"
        else:
            color = "#e6ffef"

        st.markdown(
            f"<div style='background:{color};padding:8px;border-radius:6px;margin-bottom:6px;'>"
            f"<b>{r['Empleado']}</b> — "
            f"Total: {hours_to_hhmm(r['Horas Totales'])} h | "
            f"Objetivo: {hours_to_hhmm(r['Objetivo Mes'])} h | "
            f"Sin fichar: {r['Dias Sin Fichaje']} días"
            f"</div>",
            unsafe_allow_html=True
        )

    st.success("✅ Datos procesados correctamente")

    # =============================
    # AQUÍ YA ENTRA TU GENERACIÓN
    # DE PDFs INDIVIDUALES Y GLOBAL
    # (SIN CAMBIAR NI UNA LÍNEA
    # DE LO QUE YA TENÍAS)
    # =============================




