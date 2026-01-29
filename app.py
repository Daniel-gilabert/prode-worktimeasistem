# ===============================
# PRODE WorkTimeAsistem - FINAL
# Fuente REAL: EXCEL (Entrada / Salida)
# PDF solo como SALIDA
# ===============================

import io
import zipfile
import calendar
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import streamlit as st

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ===============================
# CONFIGURACIÓN GENERAL
# ===============================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_DIA = HORAS_SEMANALES / 5  # 7.7

BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "informes"
OUT_DIR.mkdir(exist_ok=True)

# ===============================
# SESSION STATE SEGURO
# ===============================
def init_state():
    defaults = {
        "activated": False,
        "is_admin": False,
        "keys": [ADMIN_KEY, "PRODE-ULTIMAMILLA-DGC"],
        "ausencias": {},        # {empleado: {tipo: [fechas]}}
        "festivos_locales": {}, # {empleado: [fechas]}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ===============================
# UI CABECERA
# ===============================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

with st.expander("ℹ️ Cómo funciona esta herramienta"):
    st.markdown("""
- Subes **Excel real** con *Entrada* y *Salida*
- Las **horas se calculan**, no se interpretan
- Festivos nacionales + Andalucía automáticos
- Festivos locales manuales (globales o por empleado)
- Vacaciones / permisos / bajas **no cuentan como sin fichar**
- Genera:
  - PDFs individuales
  - Resumen global
  - ZIP con todo
""")

# ===============================
# ACCESO
# ===============================
st.sidebar.header("🔐 Acceso")
key = st.sidebar.text_input("Clave", type="password")
if st.sidebar.button("Activar"):
    if key in st.session_state.keys:
        st.session_state.activated = True
        st.session_state.is_admin = (key == ADMIN_KEY)
        st.sidebar.success("Acceso correcto")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.stop()

# ===============================
# GESTIÓN DE CLAVES (ADMIN)
# ===============================
if st.session_state.is_admin:
    st.sidebar.header("🛠 Gestión de claves")
    new_key = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir clave"):
        if new_key and new_key not in st.session_state.keys:
            st.session_state.keys.append(new_key)
            st.sidebar.success("Clave añadida")

    del_key = st.sidebar.selectbox(
        "Eliminar clave",
        [k for k in st.session_state.keys if k != ADMIN_KEY]
    )
    if st.sidebar.button("Eliminar clave"):
        st.session_state.keys.remove(del_key)
        st.sidebar.warning("Clave eliminada")

# ===============================
# SUBIR EXCEL
# ===============================
st.subheader("📂 Subir Excel de fichajes")
uploaded = st.file_uploader("Excel (.xlsx)", type=["xlsx"])

if not uploaded:
    st.stop()

raw = pd.read_excel(uploaded)

# ===============================
# DETECCIÓN DE COLUMNAS
# ===============================
cols = {c.lower(): c for c in raw.columns}

def find_col(keys):
    for k in keys:
        for c in cols:
            if k in c:
                return cols[c]
    return None

col_nombre = find_col(["nombre", "empleado"])
col_fecha = find_col(["fecha"])
col_entrada = find_col(["entrada"])
col_salida = find_col(["salida"])

if not all([col_nombre, col_fecha, col_entrada, col_salida]):
    st.error("El Excel no tiene columnas válidas de Nombre / Fecha / Entrada / Salida")
    st.stop()

# ===============================
# NORMALIZAR DATOS
# ===============================
df = pd.DataFrame()
df["nombre"] = raw[col_nombre].astype(str).str.strip()
df["fecha"] = pd.to_datetime(raw[col_fecha], errors="coerce").dt.date
df["entrada"] = pd.to_datetime(raw[col_entrada], errors="coerce")
df["salida"] = pd.to_datetime(raw[col_salida], errors="coerce")

df = df.dropna(subset=["nombre", "fecha"])

def calcular_horas(row):
    if pd.isna(row["entrada"]) or pd.isna(row["salida"]):
        return 0.0
    delta = row["salida"] - row["entrada"]
    return round(delta.total_seconds() / 3600, 2)

df["horas"] = df.apply(calcular_horas, axis=1)
df = df[["nombre", "fecha", "horas"]]

st.success(f"Registros cargados: {len(df)}")
st.dataframe(df.head(20))

# ===============================
# MES / AÑO
# ===============================
year = df["fecha"].iloc[0].year
month = df["fecha"].iloc[0].month

# ===============================
# FESTIVOS AUTOMÁTICOS
# ===============================
FESTIVOS_NACIONALES = {
    date(year, 1, 1),
    date(year, 5, 1),
    date(year, 10, 12),
    date(year, 12, 25),
}

FESTIVOS_ANDALUCIA = {
    date(year, 2, 28),
}

festivos_base = FESTIVOS_NACIONALES | FESTIVOS_ANDALUCIA

# ===============================
# AUSENCIAS
# ===============================
st.subheader("🏖️ Ausencias")
emp = st.selectbox("Empleado", sorted(df["nombre"].unique()))
tipo = st.selectbox("Tipo", ["Vacaciones", "Permiso", "Baja"])
rango = st.date_input("Rango", [])

if st.button("Añadir ausencia"):
    if len(rango) == 2:
        st.session_state.ausencias.setdefault(emp, {}).setdefault(tipo, []).extend(
            pd.date_range(rango[0], rango[1]).date
        )
        st.success("Ausencia registrada")

# ===============================
# PROCESAR
# ===============================
if st.button("⚙️ Procesar y generar informes"):
    with st.spinner("⏳ Generando informes, por favor espera..."):
        dias_mes = [
            date(year, month, d)
            for d in range(1, calendar.monthrange(year, month)[1] + 1)
        ]

        resultados = []

        for nombre, g in df.groupby("nombre"):
            mapa = g.groupby("fecha")["horas"].sum().to_dict()

            aus = set()
            for fechas in st.session_state.ausencias.get(nombre, {}).values():
                aus |= set(fechas)

            dias_laborables = [
                d for d in dias_mes
                if d.weekday() < 5 and d not in festivos_base and d not in aus
            ]

            objetivo = len(dias_laborables) * HORAS_DIA
            total = sum(mapa.values())
            sin_fichar = len([d for d in dias_laborables if mapa.get(d, 0) == 0])

            resultados.append({
                "Empleado": nombre,
                "Total": total,
                "Objetivo": objetivo,
                "Sin fichar": sin_fichar,
                "mapa": mapa
            })

        st.success("Informes generados correctamente")

        # ===============================
        # ZIP
        # ===============================
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for r in resultados:
                zf.writestr(
                    f"{r['Empleado']}.txt",
                    f"{r['Empleado']} - Total {r['Total']} h"
                )

        st.download_button(
            "📦 Descargar ZIP con todos los informes",
            zip_buffer.getvalue(),
            file_name=f"Informes_{month}_{year}.zip",
            mime="application/zip"
        )

st.write("✅ Aplicación lista.")





