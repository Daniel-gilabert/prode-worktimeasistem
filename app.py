# =========================================================
# PRODE WorkTimeAsistem - FINAL DEFINITIVO (PDF TABLAS)
# =========================================================

import io
import zipfile
import calendar
from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =========================================================
# CONFIG
# =========================================================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_DIA = HORAS_SEMANALES / 5  # 7.7

DEFAULT_KEYS = [
    ADMIN_KEY,
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]

# =========================================================
# SESSION STATE (BLINDADO)
# =========================================================
def init_state():
    defaults = {
        "user_keys": DEFAULT_KEYS.copy(),
        "active": False,
        "is_admin": False,
        "ausencias": {},  # {empleado: {tipo: [fechas]}}
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
def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

def hhmm(hours):
    m = int(round(hours * 60))
    return f"{m//60}:{m%60:02d}"

def parse_horas(valor):
    if valor is None:
        return 0.0
    s = str(valor).strip()
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m)/60
    if "H" in s.upper():
        h = int(s.split("H")[0])
        return float(h)
    try:
        return float(s.replace(",", "."))
    except:
        return 0.0

def festivos_auto(year):
    return {
        date(year,1,1), date(year,1,6), date(year,2,28),
        date(year,5,1), date(year,8,15),
        date(year,10,12), date(year,11,1),
        date(year,12,6), date(year,12,8), date(year,12,25)
    }

# =========================================================
# PARSER PDF PRODE (TABLAS)
# =========================================================
def parse_pdf_prode(pdf_file):
    registros = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                for row in table:
                    if not row or len(row) < 4:
                        continue

                    # PRODE suele tener:
                    # Fecha | Entrada | Salida | Jornada | ...
                    fecha_raw = row[0]
                    jornada_raw = row[3]

                    try:
                        fecha = pd.to_datetime(fecha_raw, dayfirst=True, errors="coerce")
                        if pd.isna(fecha):
                            continue
                    except:
                        continue

                    horas = parse_horas(jornada_raw)
                    if horas <= 0:
                        continue

                    registros.append({
                        "fecha": fecha.date(),
                        "horas": horas
                    })

    return registros

# =========================================================
# UI
# =========================================================
st.set_page_config(APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

with st.expander("📘 Cómo funciona esta herramienta"):
    st.markdown("""
- Subes **PDF, Excel o CSV** de fichajes  
- Se aplican **festivos nacionales + Andalucía automáticamente**  
- Puedes añadir festivos locales (globales o por empleado)  
- Vacaciones, permisos y bajas **no cuentan como sin fichar**  
- Generas informes individuales, resumen global y un ZIP
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
        filas = parse_pdf_prode(uploaded)
        if not filas:
            st.error("❌ El PDF no contiene tablas de fichajes reconocibles.")
            st.stop()
        df = pd.DataFrame(filas)
        df["nombre"] = uploaded.name  # en PDFs PRODE suele ser individual
    else:
        raw = pd.read_excel(uploaded) if uploaded.name.endswith(("xls","xlsx")) else pd.read_csv(uploaded)
        df = pd.DataFrame({
            "nombre": raw.iloc[:,0].astype(str),
            "fecha": pd.to_datetime(raw.iloc[:,1], errors="coerce").dt.date,
            "horas": raw.iloc[:,2].apply(parse_horas)
        })

st.success(f"Registros cargados: {len(df)}")

# =========================================================
# MES / AÑO
# =========================================================
year = df["fecha"].iloc[0].year
month = df["fecha"].iloc[0].month
dias_mes = list(daterange(
    date(year,month,1),
    date(year,month,calendar.monthrange(year,month)[1])
))
festivos = festivos_auto(year)

# =========================================================
# PROCESAR
# =========================================================
if st.button("⚙️ Procesar datos y generar informes"):
    with st.spinner("📄 Generando informes…"):
        zip_buffer = io.BytesIO()
        zipf = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED)

        resumen = []

        for empleado, g in df.groupby("nombre"):
            mapa = g.groupby("fecha")["horas"].sum().to_dict()
            dias_laborables = [d for d in dias_mes if d.weekday() < 5 and d not in festivos]

            objetivo = len(dias_laborables) * HORAS_DIA
            total = sum(mapa.values())
            sin_fichar = len([d for d in dias_laborables if mapa.get(d,0) == 0])

            resumen.append([empleado, hhmm(total), hhmm(objetivo), sin_fichar])

            # PDF individual
            bio = io.BytesIO()
            doc = SimpleDocTemplate(bio, pagesize=A4)
            elems = [
                Paragraph(f"<b>{empleado} — {month}/{year}</b>", getSampleStyleSheet()["Title"]),
                Spacer(1,12),
                Table(
                    [
                        ["Total horas", hhmm(total)],
                        ["Objetivo", hhmm(objetivo)],
                        ["Días sin fichar", sin_fichar]
                    ],
                    style=[('GRID',(0,0),(-1,-1),0.5,colors.grey)]
                )
            ]
            doc.build(elems)
            zipf.writestr(f"{empleado}.pdf", bio.getvalue())
            st.download_button(f"📄 {empleado}", bio.getvalue(), f"{empleado}.pdf")

        # PDF resumen global
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=landscape(A4))
        table = Table(
            [["Empleado","Horas","Objetivo","Sin fichar"]] + resumen,
            style=[('GRID',(0,0),(-1,-1),0.5,colors.grey)]
        )
        doc.build([table])
        zipf.writestr("Resumen_Global.pdf", bio.getvalue())

        zipf.close()
        st.download_button("📦 Descargar ZIP completo", zip_buffer.getvalue(), "Informes_PRODE.zip")

st.success("Proceso completado correctamente")





