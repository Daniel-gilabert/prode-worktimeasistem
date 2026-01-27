# app.py
"""
PRODE WorkTimeAsistem — ANALIZADOR AUDITABLE 2026
NO registra fichajes.
NO modifica datos de origen.
Analiza Excel / CSV / PDF de terceros para detectar riesgos legales.
"""

# =============================
# IMPORTS
# =============================
import os
import io
import re
import calendar
import hashlib
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
from reportlab.lib.pagesizes import A4
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
BASE_DIR.mkdir(exist_ok=True)

# =============================
# SESSION STATE INIT (CLAVE)
# =============================
if "activated" not in st.session_state:
    st.session_state.activated = False

if "current_key" not in st.session_state:
    st.session_state.current_key = ""

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
    s = str(s).strip().upper()
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m)/60
    h = re.findall(r"(\d+)H", s)
    m = re.findall(r"(\d+)M", s)
    return (int(h[0]) if h else 0) + (int(m[0]) if m else 0)/60

def hours_to_hhmm(h):
    if h is None or (isinstance(h, float) and np.isnan(h)):
        return "0:00"
    total_min = int(round(h * 60))
    return f"{total_min//60}:{total_min%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

# =============================
# TRAZABILIDAD
# =============================
def calcular_hash_archivo(file_obj):
    file_obj.seek(0)
    h = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return h

# =============================
# AUDITORÍAS 2026
# =============================
def detectar_sobrejornada_diaria(mapa, objetivo):
    return [d for d, h in mapa.items() if h > objetivo]

def detectar_exceso_semanal(mapa, max_sem):
    semanas = {}
    for d, h in mapa.items():
        y, w, _ = d.isocalendar()
        semanas.setdefault((y, w), 0)
        semanas[(y, w)] += h
    return [
        {"año": y, "semana": w, "horas": h}
        for (y, w), h in semanas.items()
        if h > max_sem
    ]

def detectar_jornadas_sin_pausa(mapa, umbral=6):
    return [d for d, h in mapa.items() if h >= umbral]

def registrar_auditoria(periodo, usuario, resumen):
    path = BASE_DIR / "auditorias.csv"
    fila = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "periodo": periodo,
        "usuario": usuario,
        "empleados_analizados": len(resumen),
        "alertas_sin_fichar": sum(1 for r in resumen if r["Dias Sin Fichaje"] > 0)
    }
    df = pd.DataFrame([fila])
    if path.exists():
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        df.to_csv(path, index=False)

# =============================
# PARSER PDF (INFORME PRESENCIA)
# =============================
def parse_pdf_fichajes(pdf_file):
    registros = []
    empleado = None
    patron = re.compile(r"(\d{2}-\w{3}\.-\d{2}).+?([\dHMS ]+)")
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if line.startswith("Nombre:"):
                    empleado = line.replace("Nombre:", "").strip()
                m = patron.search(line)
                if m and empleado:
                    fecha = pd.to_datetime(m.group(1), dayfirst=True, errors="coerce")
                    horas = time_str_to_hours(m.group(2))
                    if pd.notna(fecha):
                        registros.append({
                            "nombre": empleado,
                            "fecha": fecha.date(),
                            "horas": horas
                        })
    return pd.DataFrame(registros)

# =============================
# UI — CABECERA
# =============================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title("🏢 PRODE WorkTimeAsistem")
st.caption("Analizador auditable 2026 — NO registra fichajes · NO modifica datos")

# =============================
# AUTENTICACIÓN (SIN BLOQUEAR UI)
# =============================
st.sidebar.header("🔐 Acceso")
key_input = st.sidebar.text_input("Introduce la clave", type="password")

if st.sidebar.button("Activar"):
    if key_input.strip():
        st.session_state.activated = True
        st.session_state.current_key = key_input.strip()
        st.sidebar.success("Acceso activado ✅")
    else:
        st.sidebar.error("Introduce una clave válida")

if not st.session_state.activated:
    st.info("🔒 Introduce una clave en el panel lateral para comenzar.")

# =============================
# BLOQUEO FUNCIONAL (CORRECTO)
# =============================
if not st.session_state.activated:
    st.stop()

# =============================
# SUBIDA DE ARCHIVO
# =============================
st.subheader("📂 Subir archivo de fichajes")
uploaded = st.file_uploader(
    "Excel / CSV / PDF procedente de la herramienta de fichaje",
    type=["xlsx", "xls", "csv", "pdf"]
)

if not uploaded:
    st.stop()

# =============================
# METADATOS DE IMPORTACIÓN
# =============================
metadata = {
    "archivo": uploaded.name,
    "hash": calcular_hash_archivo(uploaded),
    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "usuario": st.session_state.current_key
}

# =============================
# LECTURA ARCHIVO
# =============================
try:
    if uploaded.name.lower().endswith(".pdf"):
        df = parse_pdf_fichajes(uploaded)
    elif uploaded.name.lower().endswith((".xls", ".xlsx")):
        raw = pd.read_excel(uploaded)
        df = pd.DataFrame({
            "nombre": raw.iloc[:, 0].astype(str).str.strip(),
            "fecha": pd.to_datetime(raw.iloc[:, 1], errors="coerce").dt.date,
            "horas": raw.iloc[:, 2].apply(time_str_to_hours)
        })
    else:
        raw = pd.read_csv(uploaded, sep=None, engine="python")
        df = pd.DataFrame({
            "nombre": raw.iloc[:, 0].astype(str).str.strip(),
            "fecha": pd.to_datetime(raw.iloc[:, 1], errors="coerce").dt.date,
            "horas": raw.iloc[:, 2].apply(time_str_to_hours)
        })
except Exception as e:
    st.error(f"Error leyendo archivo: {e}")
    st.stop()

df = df.dropna(subset=["nombre", "fecha"])
st.success(f"Registros cargados: {len(df)}")

# =============================
# PERIODO
# =============================
month = df["fecha"].apply(lambda d: d.month).mode()[0]
year = df["fecha"].apply(lambda d: d.year).mode()[0]
periodo = f"{month:02d}/{year}"
st.info(f"📅 Periodo analizado: {periodo}")

# =============================
# PROCESADO
# =============================
resumen = []

for nombre, g in df.groupby("nombre"):
    mapa = g.groupby("fecha")["horas"].sum().to_dict()
    dias_mes = list(daterange(
        date(year, month, 1),
        date(year, month, calendar.monthrange(year, month)[1])
    ))
    dias_laborables = [d for d in dias_mes if d.weekday() < 5]

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
        "Dias Sin Fichaje": len(dias_sin),
        "Fechas Sin Fichar": dias_sin,
        "Sobrejornada Diaria": detectar_sobrejornada_diaria(mapa, HORAS_LABORALES_DIA),
        "Excesos Semanales": detectar_exceso_semanal(mapa, HORAS_SEMANALES),
        "Jornadas Sin Pausa": detectar_jornadas_sin_pausa(mapa)
    })

registrar_auditoria(periodo, st.session_state.current_key, resumen)

# =============================
# UI RESULTADOS
# =============================
st.subheader("📊 Resultado del análisis")

for r in resumen:
    color = "#ffd6d6" if r["Dias Sin Fichaje"] > 3 else "#e6ffef"
    st.markdown(
        f"""
        <div style="background:{color};padding:8px;border-radius:6px;margin-bottom:6px;">
        <b>{r['Empleado']}</b><br>
        Horas: {hours_to_hhmm(r['Horas Totales'])} / Objetivo: {hours_to_hhmm(r['Objetivo Mes'])}<br>
        Días sin fichar: {r['Dias Sin Fichaje']}<br>
        Sobrejornadas diarias: {len(r['Sobrejornada Diaria'])}<br>
        Excesos semanales: {len(r['Excesos Semanales'])}
        </div>
        """,
        unsafe_allow_html=True
    )

# =============================
# PDF GLOBAL
# =============================
def generar_pdf_global(resumen, metadata):
    bio = io.BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph(
        f"<b>Informe de Análisis del Registro Horario</b><br/>Periodo: {periodo}",
        styles["Title"]
    ))
    elems.append(Spacer(1, 12))

    elems.append(Paragraph(
        f"""
        <font size=9>
        Archivo analizado: {metadata['archivo']}<br/>
        Hash SHA256: {metadata['hash']}<br/>
        Fecha importación: {metadata['fecha']}<br/>
        Usuario: {metadata['usuario']}<br/><br/>
        <b>Nota legal:</b> PRODE WorkTimeAsistem analiza registros generados por sistemas externos.
        No registra ni modifica fichajes (art. 34.9 ET).
        </font>
        """,
        styles["Normal"]
    ))
    elems.append(Spacer(1, 12))

    data = [["Empleado", "Horas", "Objetivo", "Días sin fichar"]]
    for r in resumen:
        data.append([
            r["Empleado"],
            hours_to_hhmm(r["Horas Totales"]),
            hours_to_hhmm(r["Objetivo Mes"]),
            str(r["Dias Sin Fichaje"])
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('ALIGN', (1,1), (-1,-1), 'CENTER')
    ]))
    elems.append(table)

    doc.build(elems)
    bio.seek(0)
    return bio

pdf = generar_pdf_global(resumen, metadata)

st.download_button(
    "📘 Descargar informe global (PDF)",
    data=pdf.getvalue(),
    file_name=f"Analisis_Registro_{periodo.replace('/','_')}.pdf",
    mime="application/pdf"
)

st.success("✅ Análisis completado y auditoría registrada.")


