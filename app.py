# app.py — PRODE WorkTimeAsistem (FINAL DEFINITIVO)

import io, re, calendar
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

BASE_DIR = Path(__file__).parent.resolve()
INFORMES_DIR = BASE_DIR / "informes"
INFORMES_DIR.mkdir(exist_ok=True)

# =====================================================
# HELPERS
# =====================================================
def safe_parse_date(x):
    try: return pd.to_datetime(x).date()
    except: return None

def hours_to_hhmm(h):
    m = int(round(h*60))
    return f"{m//60}:{m%60:02d}"

def daterange(a,b):
    for n in range((b-a).days+1):
        yield a+timedelta(n)

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
    rows=[]
    emp=None
    with pdfplumber.open(pdf) as p:
        for pg in p.pages:
            t = pg.extract_text()
            if not t: continue
            for l in t.split("\n"):
                if l.startswith("Nombre:"):
                    emp = l.replace("Nombre:","").strip()
                m = patron.search(l)
                if m and emp:
                    d,mes,y,h,mi,s = m.groups()
                    fecha = datetime.strptime(
                        f"{d}/{meses[mes.lower()]}/20{y}",
                        "%d/%m/%Y"
                    ).date()
                    horas = int(h)+int(mi)/60+int(s)/3600
                    rows.append({"nombre":emp,"fecha":fecha,"horas":horas})
    return pd.DataFrame(rows)

# =====================================================
# STREAMLIT UI
# =====================================================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

# ---------------- LOGIN ----------------
if "activated" not in st.session_state:
    st.session_state.activated=False
    st.session_state.keys=DEFAULT_KEYS.copy()
    st.session_state.ausencias={}
    st.session_state.festivos_personales={}

st.sidebar.header("🔐 Acceso")
k = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if k in st.session_state.keys:
        st.session_state.activated=True
        st.session_state.is_admin=(k==ADMIN_KEY)
        st.sidebar.success("Acceso correcto")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.stop()

# ---------------- ADMIN ----------------
if st.session_state.is_admin:
    st.sidebar.subheader("🛠 Admin")
    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir clave"):
        if nueva and nueva not in st.session_state.keys:
            st.session_state.keys.append(nueva)
            st.sidebar.success("Clave añadida")
    borrar = st.sidebar.selectbox("Eliminar clave", st.session_state.keys)
    if st.sidebar.button("Eliminar"):
        if borrar!=ADMIN_KEY:
            st.session_state.keys.remove(borrar)
            st.sidebar.warning("Clave eliminada")

# ---------------- UPLOAD ----------------
uploaded = st.file_uploader(
    "Sube fichero de fichajes (PDF / Excel / CSV)",
    type=["pdf","xlsx","xls","csv"]
)
if not uploaded: st.stop()

if uploaded.name.lower().endswith(".pdf"):
    df = parse_pdf_fichajes(uploaded)
elif uploaded.name.lower().endswith((".xls",".xlsx")):
    df = pd.read_excel(uploaded)
    df.columns=["nombre","fecha","horas"]
else:
    df = pd.read_csv(uploaded)
    df.columns=["nombre","fecha","horas"]

df["fecha"]=pd.to_datetime(df["fecha"]).dt.date
st.success(f"Registros cargados: {len(df)}")
st.dataframe(df)

# ---------------- AUSENCIAS ----------------
st.subheader("🏖️ Ausencias")
emp = st.selectbox("Empleado", sorted(df["nombre"].unique()))
mot = st.selectbox("Motivo", ["Vacaciones","Permiso","Baja médica"])
r = st.date_input("Rango", [])
if st.button("Añadir ausencia") and len(r)==2:
    st.session_state.ausencias.setdefault(emp,{}).setdefault(mot,[]).extend(
        list(daterange(r[0],r[1]))
    )
    st.success("Ausencia registrada")

# ---------------- FESTIVOS EXTRA ----------------
st.subheader("📅 Festivos extra por empleado")
fest = st.date_input("Festivo extra", [])
if st.button("Añadir festivo extra") and fest:
    st.session_state.festivos_personales.setdefault(emp,[]).append(fest)
    st.success("Festivo añadido")

# =====================================================
# PROCESAR
# =====================================================
if st.button("⚙️ Procesar datos y generar informes"):

    festivos = {safe_parse_date(f) for f in DEFAULT_FESTIVOS}
    festivos |= {safe_parse_date(f) for f in FESTIVOS_ANDALUCIA}

    month = df["fecha"].iloc[0].month
    year = df["fecha"].iloc[0].year
    dias_mes = list(daterange(date(year,month,1),
                    date(year,month,calendar.monthrange(year,month)[1])))

    st.subheader("📊 Resumen Global")

    for emp, g in df.groupby("nombre"):
        mapa = g.groupby("fecha")["horas"].sum().to_dict()
        aus = list(chain.from_iterable(st.session_state.ausencias.get(emp,{}).values()))
        fest_emp = set(st.session_state.festivos_personales.get(emp,[]))
        no_lab = festivos|set(aus)|fest_emp

        dias_lab = [d for d in dias_mes if d.weekday()<5 and d not in no_lab]
        obj = len(dias_lab)*HORAS_LABORALES_DIA
        total = sum(mapa.values())
        sin = len([d for d in dias_lab if d not in mapa])

        col = "#e6ffef" if sin<=2 else "#fff3cd" if sin<=4 else "#f8d7da"
        st.markdown(
            f"<div style='background:{col};padding:8px;border-radius:6px'>"
            f"<b>{emp}</b> — Total {hours_to_hhmm(total)} h | "
            f"Objetivo {hours_to_hhmm(obj)} h | Sin fichar {sin} días</div>",
            unsafe_allow_html=True
        )

    st.success("✅ Proceso completo")


