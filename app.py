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


# ------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ------------------------------------------------------------
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

LOGO_PATH = Path("assets/logo-prode.jpg")
HORAS_SEMANALES = 38.5
HORAS_DIA = HORAS_SEMANALES / 5  # 7.7 horas

DEFAULT_KEYS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-CAPITALHUMANO-ZMGR",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM"
]

FESTIVOS_NACIONALES = [
    "2025-01-01","2025-03-24","2025-04-17","2025-04-18","2025-05-01",
    "2025-05-26","2025-06-16","2025-06-23","2025-06-30","2025-07-20",
    "2025-08-07","2025-08-18","2025-10-13","2025-11-03","2025-11-17",
    "2025-12-08","2025-12-25"
]

FESTIVOS_ANDALUCIA = ["2025-02-28"]


# ------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------
def safe_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None


def time_to_hours(s):
    """Convierte 07:30 o 7.5 en horas float."""
    if pd.isna(s):
        return np.nan

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


def hours_to_hhmm(h):
    if pd.isna(h):
        return "0:00"
    total = int(round(h * 60))
    return f"{total // 60}:{total % 60:02d}"


def dates_range(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)


def ensure_month_dir(year, month):
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    nombre = meses[month - 1].capitalize()

    base = Path().resolve()
    folder = base / "informes" / f"{nombre} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ------------------------------------------------------------
# INTERFAZ STREAMLIT
# ------------------------------------------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.markdown(f"<h1 style='color:#004b7f;'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)

if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=160)

st.markdown("<h5 style='text-align:center;color:gray;'>Desarrollado por Daniel Gilabert Cantero — Fundación PRODE</h5>", unsafe_allow_html=True)
st.markdown("---")


# ------------------------------------------------------------
# SISTEMA DE ACCESO
# ------------------------------------------------------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.current_key = None
    st.session_state.is_admin = False

if "keys" not in st.session_state:
    st.session_state.keys = DEFAULT_KEYS.copy()

if "ausencias" not in st.session_state:
    st.session_state.ausencias = {}  # {empleado: {motivo: [fechas]}}


st.sidebar.header("🔐 Acceso temporal")
key_input = st.sidebar.text_input("Clave:", type="password")

if st.sidebar.button("Activar"):
    if key_input.strip() in st.session_state.keys:
        st.session_state.activated = True
        st.session_state.current_key = key_input.strip()
        st.session_state.is_admin = (key_input.strip() == ADMIN_KEY)
        st.sidebar.success("Acceso concedido ✔")
    else:
        st.sidebar.error("Clave incorrecta ❌")


if not st.session_state.activated:
    st.warning("🔒 Introduce tu clave en la barra lateral para acceder")
    st.stop()


# ------------------------------------------------------------
# PANEL ADMIN (solo PRODE-ADMIN-ADMIN)
# ------------------------------------------------------------
if st.session_state.is_admin:
    st.sidebar.subheader("🛠 Gestión de claves")
    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("➕ Añadir"):
        if nueva and nueva not in st.session_state.keys:
            st.session_state.keys.append(nueva)
            st.sidebar.success("Clave añadida")

    eliminar = st.sidebar.selectbox("Eliminar clave", [k for k in st.session_state.keys if k != ADMIN_KEY])
    if st.sidebar.button("🗑️ Borrar clave"):
        st.session_state.keys.remove(eliminar)
        st.sidebar.warning(f"Clave {eliminar} eliminada")


# ------------------------------------------------------------
# SUBIR ARCHIVO
# ------------------------------------------------------------
st.subheader("📂 Subir fichajes (.xlsx)")
archivo = st.file_uploader("Selecciona archivo Excel", type=["xlsx"])

if not archivo:
    st.info("Sube el archivo de fichajes para comenzar.")
    st.stop()


# ------------------------------------------------------------
# LEER EXCEL
# ------------------------------------------------------------
try:
    df_raw = pd.read_excel(archivo)
except Exception as e:
    st.error(f"Error leyendo archivo: {e}")
    st.stop()


cols = {c.lower().strip(): c for c in df_raw.columns}


def col(*names):
    for n in names:
        for key, orig in cols.items():
            if n.lower() in key:
                return orig
    return None


col_nom = col("apellidos y nombre", "empleado", "nombre")
col_fecha = col("fecha")
col_horas = col("tiempo trabajado", "hras", "horas")

if not col_nom or not col_fecha or not col_horas:
    st.error("No se encontraron columnas obligatorias. Revisa el archivo.")
    st.write("Columnas detectadas:", df_raw.columns)
    st.stop()


df = pd.DataFrame()
df["nombre"] = df_raw[col_nom].astype(str).str.strip()
df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce").dt.date
df["horas"] = df_raw[col_horas].apply(time_to_hours)

df = df.dropna(subset=["fecha"])


st.success(f"Datos cargados: {len(df)} registros | {df['nombre'].nunique()} empleados")


# ------------------------------------------------------------
# DETECTAR MES Y AÑO
# ------------------------------------------------------------
month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
year = int(df["fecha"].apply(lambda d: d.year).mode()[0])

folder = ensure_month_dir(year, month)
st.info(f"📁 Informes se guardarán en: {folder}")


# ------------------------------------------------------------
# FESTIVOS MANUALES
# ------------------------------------------------------------
st.subheader("📅 Festivos adicionales (opcional)")
festivos_input = st.text_input("Fechas (AAAA-MM-DD separadas por coma)")

festivos_manuales = [safe_date(x) for x in festivos_input.split(",") if safe_date(x)]


# ------------------------------------------------------------
# AUSENCIAS / VACACIONES / BAJA
# ------------------------------------------------------------
st.subheader("🏖️ Registrar ausencias por empleado")

empleado = st.selectbox("Empleado", sorted(df["nombre"].unique()))
motivo = st.selectbox("Motivo", ["Vacaciones", "Permiso", "Baja médica"])

rango = st.date_input("Rango (inicio - fin)", [])

if st.button("➕ Añadir ausencia"):
    if len(rango) == 2:
        ini, fin = rango
        st.session_state.ausencias.setdefault(empleado, {})
        st.session_state.ausencias[empleado].setdefault(motivo, [])
        st.session_state.ausencias[empleado][motivo].extend(list(dates_range(ini, fin)))
        st.success(f"Añadido: {empleado} — {motivo}")
    else:
        st.error("Selecciona un rango válido")


# ------------------------------------------------------------
# PROCESAR DATOS
# ------------------------------------------------------------
if st.button("⚙️ Generar informes"):

    festivos = set([safe_date(x) for x in FESTIVOS_NACIONALES + FESTIVOS_ANDALUCIA if safe_date(x)])
    festivos |= set(festivos_manuales)

    dias_mes = list(dates_range(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])))

    resumen = []
    alertas = []

    for nombre, g in df.groupby("nombre"):

        mapa = g.groupby("fecha")["horas"].sum().to_dict()
        total_horas = sum(mapa.values())

        aus = list(chain.from_iterable(
            st.session_state.ausencias.get(nombre, {}).values()
        ))

        no_laborables = festivos.union(aus)
        laborables = [d for d in dias_mes if d.weekday() < 5 and d not in no_laborables]

        objetivo = len(laborables) * HORAS_DIA
        diferencia = total_horas - objetivo
        extras = max(diferencia, 0)

        sin_fichar = [d for d in laborables if mapa.get(d, 0) == 0]

        resumen.append({
            "Empleado": nombre,
            "Horas": total_horas,
            "Objetivo": objetivo,
            "Dif": diferencia,
            "Extras": extras,
            "Fichados": len(laborables) - len(sin_fichar),
            "SinFichar": sin_fichar,
            "Mapa": mapa
        })

        if len(sin_fichar) > 0:
            alertas.append((nombre, len(sin_fichar)))


    # ------------------------------------------------------------
    # PDF GENERADORES
    # ------------------------------------------------------------
    styles = getSampleStyleSheet()

    def pdf_individual(r):

        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)

        elems = []

        if LOGO_PATH.exists():
            elems.append(Image(str(LOGO_PATH), width=120))
            elems.append(Spacer(1, 10))

        header = Paragraph(f"<b>Empleado:</b> {r['Empleado']} — {month}/{year}", styles['Heading2'])
        elems.append(header)
        elems.append(Spacer(1, 10))

        tabla = [
            ["Total horas", hours_to_hhmm(r["Horas"])],
            ["Objetivo", hours_to_hhmm(r["Objetivo"])],
            ["Diferencia", hours_to_hhmm(r["Dif"])],
            ["Horas extra", hours_to_hhmm(r["Extras"])],
            ["Días sin fichar", len(r["SinFichar"])]
        ]

        t = Table(tabla, colWidths=[7*cm, 4*cm])
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.grey)]))
        elems.append(t)

        elems.append(Spacer(1, 10))

        filas = [["Fecha","Horas","Tipo"]]
        for d in dias_mes:
            tipo = "Laborable"
            if d in festivos:
                tipo = "Festivo"
            if d in aus:
                tipo = next(m for m,v in st.session_state.ausencias.get(r["Empleado"], {}).items() if d in v)
            if r["Mapa"].get(d, 0) == 0 and tipo=="Laborable":
                tipo = "Sin fichar"

            filas.append([d.strftime("%d/%m/%Y"), hours_to_hhmm(r["Mapa"].get(d,0)), tipo])

        tt = Table(filas, colWidths=[4*cm,3*cm,6*cm])
        tt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.3,colors.grey)]))
        elems.append(tt)

        doc.build(elems)
        bio.seek(0)
        return bio


    # ------------------------------------------------------------
    # MOSTRAR RESUMEN
    # ------------------------------------------------------------
    st.subheader("📊 Resumen Global")

    for r in resumen:
        color = "#e6ffef"
        if len(r["SinFichar"]) > 4:
            color = "#ffdddd"
        elif len(r["SinFichar"]) > 2:
            color = "#fff3cd"

        st.markdown(
            f"<div style='background:{color};padding:8px;border-radius:6px;'>"
            f"<b>{r['Empleado']}</b> — Total {hours_to_hhmm(r['Horas'])}h — "
            f"Objetivo {hours_to_hhmm(r['Objetivo'])}h — "
            f"{len(r['SinFichar'])} días sin fichar"
            f"</div>", unsafe_allow_html=True
        )

    # ------------------------------------------------------------
    # PDF INDIVIDUALES
    # ------------------------------------------------------------
    st.subheader("📄 Descargas individuales")

    for r in resumen:
        pdf = pdf_individual(r)
        fname = f"Asistencia_{r['Empleado'].replace(' ','_')}_{year}_{month}.pdf"

        with open(folder / fname, "wb") as f:
            f.write(pdf.getvalue())

        st.download_button(
            label=f"Descargar {r['Empleado']}",
            data=pdf.getvalue(),
            file_name=fname,
            mime="application/pdf"
        )

    st.success("✅ Informes generados correctamente")



