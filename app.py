# -------------------------------------------------------------
#  PRODE WorkTimeAsistem - Versión corregida para Streamlit Cloud
# -------------------------------------------------------------

import os
import io
import calendar
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


# -------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

LOGO_FILENAME = "logo-prode.jpg"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7

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


# -------------------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------------------
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
        try:
            h, m = s.split(":")
            return int(h) + int(m) / 60
        except:
            pass

    s2 = s.replace(",", ".")
    try:
        return float(s2)
    except:
        return np.nan


def hours_to_hhmm(hours):
    if hours is None or (isinstance(hours, float) and np.isnan(hours)):
        return "0:00"
    total_min = int(round(float(hours) * 60))
    h = total_min // 60
    m = total_min % 60
    return f"{h}:{m:02d}"


def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)


def create_month_folder_from_date(year, month):
    meses = [
        "enero","febrero","marzo","abril","mayo","junio",
        "julio","agosto","septiembre","octubre","noviembre","diciembre"
    ]
    mes_nombre = meses[month-1].capitalize()
    base = Path("informes")
    folder = base / f"{mes_nombre} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# -------------------------------------------------------------
# INTERFAZ STREAMLIT
# -------------------------------------------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")

st.markdown(f"<h1 style='color:#003366;'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)

if Path(LOGO_FILENAME).exists():
    st.image(LOGO_FILENAME, width=140)

st.markdown("<h5 style='text-align:center;color:gray;'>Desarrollado por Daniel Gilabert Cantero — Fundación PRODE</h5>", unsafe_allow_html=True)
st.markdown("---")


# -------------------------------------------------------------
# SESIONES
# -------------------------------------------------------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.current_key = None
    st.session_state.is_admin = False

if "user_keys" not in st.session_state:
    st.session_state.user_keys = DEFAULT_KEYS.copy()

if "dias_por_empleado" not in st.session_state:
    st.session_state.dias_por_empleado = {}


# -------------------------------------------------------------
# CONTROL DE ACCESO
# -------------------------------------------------------------
st.sidebar.header("🔐 Acceso")

key_input = st.sidebar.text_input("Introduce tu clave:", type="password")

if st.sidebar.button("Activar"):
    if key_input.strip() in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.current_key = key_input.strip()
        st.session_state.is_admin = (key_input.strip() == ADMIN_KEY)
        st.sidebar.success("Acceso concedido ✔")
    else:
        st.sidebar.error("Clave incorrecta ❌")


# ADMINISTRADOR
if st.session_state.is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠 Gestión de claves")

    nueva = st.sidebar.text_input("Nueva clave")

    if st.sidebar.button("➕ Añadir clave"):
        if nueva and nueva not in st.session_state.user_keys:
            st.session_state.user_keys.append(nueva)
            st.sidebar.success("Clave añadida ✔")

    eliminar = st.sidebar.selectbox("Eliminar clave", [k for k in st.session_state.user_keys if k != ADMIN_KEY])

    if st.sidebar.button("🗑️ Eliminar clave"):
        st.session_state.user_keys.remove(eliminar)
        st.sidebar.warning("Clave eliminada")


if not st.session_state.activated:
    st.warning("Introduce tu clave para acceder.")
    st.stop()


# -------------------------------------------------------------
# SUBIR ARCHIVO
# -------------------------------------------------------------
st.subheader("📂 Subir archivo de fichajes")

uploaded = st.file_uploader("Selecciona el archivo", type=["xlsx", "xls", "csv"])

if not uploaded:
    st.info("Sube un archivo para continuar.")
    st.stop()


# -------------------------------------------------------------
# PROCESAR ARCHIVO
# -------------------------------------------------------------
try:
    if uploaded.name.lower().endswith(("xls", "xlsx")):
        df_raw = pd.read_excel(uploaded)
    else:
        uploaded.seek(0)
        df_raw = pd.read_csv(uploaded, sep=None, engine="python")
except Exception as e:
    st.error(f"No se puede leer el archivo: {e}")
    st.stop()


# Normalizar columnas
cols_map_lower = {c.lower().strip(): c for c in df_raw.columns}

def find_col(possible_names):
    for p in possible_names:
        for k, orig in cols_map_lower.items():
            if p.lower() in k:
                return orig
    return None


col_nombre = find_col(["apellidos y nombre", "nombre", "empleado"])
col_fecha = find_col(["fecha"])
col_horas = find_col(["tiempo", "horas", "tiempo trabajado"])

if not col_nombre or not col_fecha or not col_horas:
    st.error("No se encontraron las columnas necesarias.")
    st.stop()


df = pd.DataFrame()
df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
df["fecha_orig"] = df_raw[col_fecha]

df["fecha"] = pd.to_datetime(df["fecha_orig"], errors="coerce").dt.date
df["horas"] = df_raw[col_horas].apply(time_str_to_hours)

df = df.dropna(subset=["fecha"])
df = df[df["nombre"] != ""]


# -------------------------------------------------------------
# DETECTAR MES
# -------------------------------------------------------------
month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
year = int(df["fecha"].apply(lambda d: d.year).mode()[0])

meses_sp = [
    "enero","febrero","marzo","abril","mayo","junio",
    "julio","agosto","septiembre","octubre","noviembre","diciembre"
]
month_name = meses_sp[month-1].capitalize()

folder = create_month_folder_from_date(year, month)
st.info(f"Los informes se guardarán en: {folder}")


# -------------------------------------------------------------
# CONTROL DE FESTIVOS Y AUSENCIAS
# -------------------------------------------------------------
st.subheader("📅 Festivos adicionales")
festivos_input = st.text_input("Festivos (AAAA-MM-DD separados por coma)")

manual_festivos = []
for token in [t.strip() for t in festivos_input.split(",") if t.strip()]:
    d = safe_parse_date(token)
    if d:
        manual_festivos.append(d)


st.subheader("🏖️ Ausencias por empleado")

empleado_sel = st.selectbox("Empleado", sorted(df["nombre"].unique()))
motivo_sel = st.selectbox("Motivo", ["Vacaciones", "Permiso", "Baja médica"])
rango = st.date_input("Rango de fechas", [])

if st.button("➕ Añadir ausencia"):
    if len(rango) == 2:
        desde, hasta = rango
        st.session_state.dias_por_empleado.setdefault(empleado_sel, {})
        st.session_state.dias_por_empleado[empleado_sel].setdefault(motivo_sel, [])
        st.session_state.dias_por_empleado[empleado_sel][motivo_sel].extend(list(daterange(desde, hasta)))
        st.success("Ausencia añadida ✔")


umbral_alerta = st.sidebar.slider("Umbral días sin fichar", 1, 10, 3)


# -------------------------------------------------------------
# PROCESAR Y GENERAR INFORMES
# -------------------------------------------------------------
if st.button("⚙️ Procesar datos y generar informes"):

    resumen_empleados = []

    for nombre, g in df.groupby("nombre"):
        mapa = g.groupby("fecha")["horas"].sum().to_dict()
        total_horas = sum(mapa.values())
        resumen_empleados.append({
            "nombre": nombre,
            "mapa_horas": mapa,
            "total_horas": total_horas
        })

    dias_mes = list(daterange(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])))

    festivos_obj = set(safe_parse_date(d) for d in DEFAULT_FESTIVOS + FESTIVOS_ANDALUCIA if safe_parse_date(d))

    for d in manual_festivos:
        festivos_obj.add(d)

    global_data = []

    for r in resumen_empleados:
        nombre = r["nombre"]

        ausencias = list(chain.from_iterable(
            st.session_state.dias_por_empleado.get(nombre, {}).values()
        )) if nombre in st.session_state.dias_por_empleado else []

        dias_no_laborables = festivos_obj.union(ausencias)
        dias_laborables = [d for d in dias_mes if d.weekday() < 5 and d not in dias_no_laborables]

        objetivo_mes = len(dias_laborables) * HORAS_LABORALES_DIA
        diferencia = r["total_horas"] - objetivo_mes
        horas_extra = max(0, diferencia)

        dias_sin_fichar = [d for d in dias_laborables if d not in r["mapa_horas"] or r["mapa_horas"].get(d, 0) == 0]

        global_data.append({
            "Empleado": nombre,
            "Horas Totales": r["total_horas"],
            "Objetivo Mes": objetivo_mes,
            "Diferencia": diferencia,
            "Horas Extra": horas_extra,
            "Dias Sin Fichar": len(dias_sin_fichar),
            "Fechas Sin Fichar": dias_sin_fichar,
            "Ausencias": ausencias,
            "mapa_horas": r["mapa_horas"]
        })

    st.success("Procesado completado ✔")

    # ---------------------------------------------
    # DESCARGAS
    # ---------------------------------------------

    st.subheader("📥 Descargas individuales")

    for r in global_data:
        pdf_bytes = io.BytesIO()
        pdf = SimpleDocTemplate(pdf_bytes, pagesize=A4)
        elements = []

        elements.append(Paragraph(f"<b>{r['Empleado']}</b>", getSampleStyleSheet()["Title"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Resumen mensual:", getSampleStyleSheet()["Heading3"]))

        summary = [
            ["Horas Totales", hours_to_hhmm(r["Horas Totales"])],
            ["Objetivo", hours_to_hhmm(r["Objetivo Mes"])],
            ["Diferencia", hours_to_hhmm(r["Diferencia"])],
            ["Horas Extra", hours_to_hhmm(r["Horas Extra"])],
            ["Días sin fichar", r["Dias Sin Fichar"]]
        ]

        table = Table(summary)
        table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.grey)]))
        elements.append(table)

        pdf.build(elements)
        pdf_bytes.seek(0)

        st.download_button(
            f"📄 Descargar {r['Empleado']}",
            data=pdf_bytes,
            file_name=f"informe_{r['Empleado']}.pdf"
        )

    st.success("Todos los informes están listos ✔")

