# app.py
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

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =============================
# CONFIG
# =============================
APP_NAME = "PRODE WorkTimeAsistem"
HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

BASE_DIR = Path(__file__).parent.resolve()

CURRENT_YEAR = datetime.now().year

DEFAULT_FESTIVOS = [
    f"{CURRENT_YEAR}-01-01",
    f"{CURRENT_YEAR}-01-06",
    f"{CURRENT_YEAR}-05-01",
    f"{CURRENT_YEAR}-08-15",
    f"{CURRENT_YEAR}-10-12",
    f"{CURRENT_YEAR}-11-01",
    f"{CURRENT_YEAR}-12-06",
    f"{CURRENT_YEAR}-12-08",
    f"{CURRENT_YEAR}-12-25",
]

FESTIVOS_ANDALUCIA = [
    f"{CURRENT_YEAR}-02-28"
]

COLOR_PRIMARY = "#12486C"
COLOR_SECOND = "#2F709F"

COLOR_HORA_EXTRA = "#d8fcd8"
COLOR_DEFICIT = "#ffe4b2"
COLOR_SIN_GRAVE = "#ffb3b3"
COLOR_FESTIVO = "#cfe3ff"
COLOR_VACACIONES = "#e4ceff"
COLOR_PERMISO = "#ffd6f3"
COLOR_BAJA = "#c9f2e7"

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
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m) / 60
    return float(s.replace(",", "."))

def hours_to_hhmm(h):
    total = int(round(h * 60))
    return f"{total//60}:{total%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

def create_month_folder(year, month):
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    folder = BASE_DIR / "informes" / f"{meses[month-1].capitalize()} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

# =============================
# STREAMLIT
# =============================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

uploaded = st.file_uploader("📂 Subir archivo Excel o CSV", type=["xlsx","xls","csv"])
if not uploaded:
    st.stop()

# =============================
# LECTURA ARCHIVO
# =============================
df = pd.read_excel(uploaded)
df.columns = [c.lower() for c in df.columns]

df["nombre"] = df.iloc[:,0].astype(str)
df["fecha"] = pd.to_datetime(df.iloc[:,1]).dt.date
df["horas"] = df.iloc[:,2].apply(time_str_to_hours)

month = df["fecha"].iloc[0].month
year = df["fecha"].iloc[0].year

dias_mes = list(daterange(date(year, month, 1),
                           date(year, month, calendar.monthrange(year, month)[1])))

# =============================
# FESTIVOS AUTOMÁTICOS
# =============================
festivos_objetivos = {safe_parse_date(f) for f in DEFAULT_FESTIVOS}
festivos_objetivos |= {safe_parse_date(f) for f in FESTIVOS_ANDALUCIA}

# =============================
# PROCESADO
# =============================
resumen = []

for nombre, g in df.groupby("nombre"):
    mapa = g.groupby("fecha")["horas"].sum().to_dict()
    ausencias = []

    dias_laborables = [
        d for d in dias_mes
        if d.weekday() < 5 and (d not in festivos_objetivos or d in mapa)
    ]

    objetivo_mes = len(dias_laborables) * HORAS_LABORALES_DIA
    total_horas = sum(mapa.values())
    diferencia = total_horas - objetivo_mes

    dias_sin_fichar = [
        d for d in dias_laborables
        if d not in festivos_objetivos and mapa.get(d, 0) == 0
    ]

    resumen.append({
        "Empleado": nombre,
        "Horas Totales": total_horas,
        "Objetivo Mes": objetivo_mes,
        "Diferencia": diferencia,
        "Dias Sin Fichar": len(dias_sin_fichar),
        "mapa": mapa
    })

# =============================
# UI RESUMEN
# =============================
st.subheader("📊 Resumen Global")
folder = create_month_folder(year, month)

for r in resumen:
    col1, col2 = st.columns([6,1])

    with col1:
        st.markdown(
            f"<div style='background:#f8d7da;padding:8px;border-radius:6px;'>"
            f"<b>{r['Empleado']}</b> — "
            f"Total: {hours_to_hhmm(r['Horas Totales'])} | "
            f"Objetivo: {hours_to_hhmm(r['Objetivo Mes'])} | "
            f"Sin fichar: {r['Dias Sin Fichar']}"
            f"</div>",
            unsafe_allow_html=True
        )

    with col2:
        pdf_name = f"Asistencia_{r['Empleado'].replace(' ','_')}_{year}_{month}.pdf"

        def generar_pdf(entry):
            bio = io.BytesIO()
            doc = SimpleDocTemplate(bio, pagesize=A4)
            styles = getSampleStyleSheet()
            elems = []

            elems.append(Paragraph(f"<b>{entry['Empleado']}</b>", styles["Title"]))
            elems.append(Spacer(1,8))

            table_data = [["Fecha","Horas","Tipo"]]

            for d in dias_mes:
                tipo = "Laborable"

                if d.weekday() >= 5:
                    tipo = "Fin de semana"
                if d in festivos_objetivos:
                    tipo = "Festivo"

                horas = entry["mapa"].get(d, 0)

                if tipo == "Laborable" and horas == 0:
                    tipo = "Sin fichar"

                table_data.append([
                    d.strftime("%d/%m/%Y"),
                    hours_to_hhmm(horas),
                    tipo
                ])

            t = Table(table_data, colWidths=[6*cm,4*cm,6*cm])
            t.setStyle(TableStyle([
                ('GRID',(0,0),(-1,-1),0.25,colors.grey),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COLOR_PRIMARY)),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ]))

            elems.append(t)
            doc.build(elems)
            bio.seek(0)
            return bio

        pdf_bytes = generar_pdf(r)

        st.download_button(
            "⬇",
            data=pdf_bytes.getvalue(),
            file_name=pdf_name,
            mime="application/pdf"
        )

st.success("✅ Todo correcto. Festivos automáticos incluidos.")
