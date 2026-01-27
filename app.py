# app.py
"""
PRODE WorkTimeAsistem — ANALIZADOR AUDITABLE 2026
NO registra fichajes.
NO modifica datos de origen.
Analiza Excel / CSV / PDF de terceros para detectar riesgos legales.
FORMATO OFICIAL: Excel Última Milla (Apellidos y Nombre / Fecha / Tiempo trabajado)
"""

# =============================
# IMPORTS
# =============================
import io
import re
import calendar
import hashlib
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =============================
# CONFIGURACIÓN
# =============================
APP_NAME = "PRODE WorkTimeAsistem"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

BASE_DIR = Path(__file__).parent.resolve()

# =============================
# SESSION STATE INIT
# =============================
if "activated" not in st.session_state:
    st.session_state.activated = False
if "current_key" not in st.session_state:
    st.session_state.current_key = ""

# =============================
# FUNCIONES AUXILIARES
# =============================
def hours_to_hhmm(h):
    if h is None or (isinstance(h, float) and np.isnan(h)):
        return "0:00"
    total_min = int(round(h * 60))
    return f"{total_min//60}:{total_min%60:02d}"

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

def calcular_hash_archivo(file_obj):
    file_obj.seek(0)
    h = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return h

# =============================
# AUDITORÍAS
# =============================
def detectar_sobrejornada_diaria(mapa, objetivo):
    return [d for d, h in mapa.items() if h > objetivo]

def detectar_exceso_semanal(mapa, max_sem):
    semanas = {}
    for d, h in mapa.items():
        y, w, _ = d.isocalendar()
        semanas.setdefault((y, w), 0)
        semanas[(y, w)] += h
    return [(y, w, h) for (y, w), h in semanas.items() if h > max_sem]

def detectar_jornadas_sin_pausa(mapa, umbral=6):
    return [d for d, h in mapa.items() if h >= umbral]

def registrar_auditoria(periodo, usuario, resumen):
    path = BASE_DIR / "auditorias.csv"
    fila = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "periodo": periodo,
        "usuario": usuario,
        "empleados": len(resumen),
        "alertas_sin_fichar": sum(1 for r in resumen if r["Dias Sin Fichaje"] > 0)
    }
    df = pd.DataFrame([fila])
    if path.exists():
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        df.to_csv(path, index=False)

# =============================
# UI CABECERA
# =============================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title("🏢 PRODE WorkTimeAsistem")
st.caption("Analizador auditable 2026 · NO registra fichajes · NO modifica datos")

# =============================
# LOGIN SIMPLE
# =============================
st.sidebar.header("🔐 Acceso")
key_input = st.sidebar.text_input("Introduce la clave", type="password")

if st.sidebar.button("Activar"):
    if key_input.strip():
        st.session_state.activated = True
        st.session_state.current_key = key_input.strip()
        st.sidebar.success("Acceso activado ✅")
    else:
        st.sidebar.error("Clave no válida")

if not st.session_state.activated:
    st.info("🔒 Introduce una clave en el panel lateral para comenzar.")
    st.stop()

# =============================
# SUBIDA DE ARCHIVO
# =============================
st.subheader("📂 Subir Excel de fichajes (formato Última Milla)")
uploaded = st.file_uploader(
    "Excel procedente de la herramienta de fichaje",
    type=["xlsx", "xls"]
)

if not uploaded:
    st.stop()

# =============================
# METADATOS
# =============================
metadata = {
    "archivo": uploaded.name,
    "hash": calcular_hash_archivo(uploaded),
    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "usuario": st.session_state.current_key
}

# =============================
# LECTURA EXCEL (FORMATO DEFINITIVO)
# =============================
raw = pd.read_excel(uploaded)

cols = {c.lower().strip(): c for c in raw.columns}

def find_col(posibles):
    for p in posibles:
        for k, orig in cols.items():
            if p in k:
                return orig
    return None

col_nombre = find_col(["apellidos y nombre", "apellidos", "nombre"])
col_fecha = find_col(["fecha"])
col_horas = find_col(["tiempo trabajado"])

if not col_nombre or not col_fecha or not col_horas:
    st.error("❌ El Excel no corresponde al formato oficial de Última Milla.")
    st.error(f"Columnas encontradas: {list(raw.columns)}")
    st.stop()

df = pd.DataFrame()
df["nombre"] = raw[col_nombre].astype(str).str.strip()
df["fecha"] = pd.to_datetime(
    raw[col_fecha],
    errors="coerce",
    dayfirst=True
).dt.date
df["horas"] = pd.to_numeric(raw[col_horas], errors="coerce")

df = df.dropna(subset=["nombre", "fecha", "horas"])

st.success(f"Registros válidos cargados: {len(df)}")

# =============================
# PERIODO ANALIZADO
# =============================
month = df["fecha"].apply(lambda d: d.month).mode()[0]
year = df["fecha"].apply(lambda d: d.year).mode()[0]
periodo = f"{month:02d}/{year}"

st.info(f"📅 Periodo analizado: {periodo}")

# =============================
# PROCESADO PRINCIPAL
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
        "Sobrejornada Diaria": detectar_sobrejornada_diaria(mapa, HORAS_LABORALES_DIA),
        "Excesos Semanales": detectar_exceso_semanal(mapa, HORAS_SEMANALES),
        "Jornadas Largas": detectar_jornadas_sin_pausa(mapa)
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
        Fecha análisis: {metadata['fecha']}<br/>
        Usuario: {metadata['usuario']}<br/><br/>
        <b>Nota legal:</b> Este informe analiza registros generados por un sistema externo de fichaje.
        PRODE WorkTimeAsistem no registra ni modifica jornadas (art. 34.9 ET).
        </font>
        """,
        styles["Normal"]
    ))
    elems.append(Spacer(1, 12))

    data = [["Empleado", "Horas Totales", "Objetivo", "Días sin fichar"]]
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

st.success("✅ Análisis completado y auditoría registrada correctamente.")
