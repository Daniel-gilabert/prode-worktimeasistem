# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (VERSIÓN PDF + EXCEL)
Incluye:
- Lectura de Excel, CSV y PDF de Control Horario PRODE
- Generación de informes individuales y globales en PDF
- Activación por clave
- Gestión de festivos y ausencias
- (Opcional) Subida a SharePoint vía MS Graph
"""

import os
import io
import json
import calendar
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain
import re

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

# Optional MSAL / Graph integration
try:
    import msal
    import requests
    MSAL_AVAILABLE = True
except Exception:
    MSAL_AVAILABLE = False


# ============================================================
#  CONFIGURACIÓN GENERAL
# ============================================================

APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"
LOGO_FILENAME = "logo-prode.jpg"
LOGO_LOCAL_PATH = "/mnt/data/logo-prode.jpg"   # Puedes poner /assets/logo-prode.jpg

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7h por día

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

COLOR_PRIMARY = "#12486C"
COLOR_ACCENT = "#F5BD2D"
COLOR_BG = "#ECF3F9"
COLOR_SECOND = "#2F709F"
COLOR_TEXT = "#062A54"

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)


# ============================================================
#  HELPERS GENERALES
# ============================================================

def safe_parse_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def time_str_to_hours(s):
    """Convierte '7:30', '7H 30M', '7.5', etc. a horas float."""
    if pd.isna(s):
        return np.nan
    if isinstance(s, (int, float, np.integer, np.floating)):
        return float(s)

    s = str(s).strip()
    if not s:
        return np.nan

    if ":" in s:
        try:
            hh, mm = s.split(":")
            return int(hh) + int(mm)/60
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
    total_min = int(round(float(hours)*60))
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
    nombre_mes = meses[month-1].capitalize()
    folder = BASE_DIR / "informes" / f"{nombre_mes} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ============================================================
#  PARSER DE PDF — NUEVO
# ============================================================

def parse_pdf_fichajes(pdf_file):
    """
    Convierte informes PDF de Control de Presencia PRODE en un DataFrame:
    columnas: nombre, fecha, horas
    """

    registros = []
    empleado_actual = None

    patron = re.compile(
        r"(\d{2}-\w{3}\.-\d{2})\s+(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})\s+([\dHMS\s]+)"
    )

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()

            if not text:
                continue

            lines = text.split("\n")

            # Buscar nombre del empleado
            for line in lines:
                if line.startswith("Nombre:"):
                    empleado_actual = line.replace("Nombre:", "").strip()
                    break

            # Extraer los registros
            for line in lines:
                m = patron.search(line)
                if m:
                    fecha_raw, entrada, salida, jornada = m.groups()

                    try:
                        fecha = pd.to_datetime(fecha_raw, format="%d-%b.-%y", dayfirst=True).date()
                    except:
                        continue

                    H = re.findall(r"(\d+)H", jornada)
                    M = re.findall(r"(\d+)M", jornada)
                    S = re.findall(r"(\d+)S", jornada)

                    horas_num = (
                        (int(H[0]) if H else 0) +
                        (int(M[0]) if M else 0)/60 +
                        (int(S[0]) if S else 0)/3600
                    )

                    registros.append({
                        "nombre": empleado_actual,
                        "fecha": fecha,
                        "horas": horas_num
                    })

    return pd.DataFrame(registros)


# ============================================================
#  STREAMLIT UI — CABECERA
# ============================================================

st.set_page_config(page_title=APP_NAME, layout="wide")

st.markdown(f"<h1 style='color:{COLOR_PRIMARY};'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)

logo_path = None
if Path(LOGO_LOCAL_PATH).exists():
    logo_path = LOGO_LOCAL_PATH
elif (ASSETS_DIR / LOGO_FILENAME).exists():
    logo_path = str(ASSETS_DIR / LOGO_FILENAME)

if logo_path:
    st.image(logo_path, width=160)

st.markdown("<h5 style='text-align:center;color:gray;'>Desarrollado por <b>Daniel Gilabert Cantero</b> — Fundación PRODE</h5>", unsafe_allow_html=True)
st.markdown("---")


# ============================================================
#  ACTIVACIÓN (CLAVE)
# ============================================================

if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.user_keys = DEFAULT_KEYS.copy()
    st.session_state.current_key = ""
    st.session_state.is_admin = False

st.sidebar.header("🔐 Acceso (obligatorio)")
key_input = st.sidebar.text_input("Introduce tu clave:", type="password")

if st.sidebar.button("Activar"):
    if key_input in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.current_key = key_input
        st.session_state.is_admin = (key_input == ADMIN_KEY)
        st.sidebar.success("Acceso concedido.")
    else:
        st.sidebar.error("Clave incorrecta.")

if not st.session_state.activated:
    st.warning("Introduce tu clave para activar la aplicación.")
    st.stop()

# Admin para gestionar claves
if st.session_state.is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠 Administración de claves")
    newkey = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("Añadir clave"):
        if newkey and newkey not in st.session_state.user_keys:
            st.session_state.user_keys.append(newkey)
            st.sidebar.success("Clave añadida.")

    delkey = st.sidebar.selectbox("Eliminar clave", [k for k in st.session_state.user_keys if k != ADMIN_KEY])
    if st.sidebar.button("Eliminar clave"):
        st.session_state.user_keys.remove(delkey)
        st.sidebar.warning(f"Clave {delkey} eliminada.")


# ============================================================
#  SUBIDA DE ARCHIVO
# ============================================================

st.subheader("📂 Subir archivo de fichajes (.xlsx/.csv/.pdf)")
uploaded = st.file_uploader("Selecciona archivo", type=["xlsx","xls","csv","pdf"])

if not uploaded:
    st.info("Sube un archivo para continuar.")
    st.stop()


# ============================================================
#  LECTURA DE ARCHIVO (PDF / EXCEL / CSV)
# ============================================================

try:
    filename = uploaded.name.lower()

    if filename.endswith(".pdf"):
        st.info("Procesando PDF…")
        df = parse_pdf_fichajes(uploaded)

        if df.empty:
            st.error("No se pudieron leer registros del PDF.")
            st.stop()

        st.success(f"{len(df)} registros PDF importados.")

    elif filename.endswith((".xls",".xlsx")):
        st.info("Procesando Excel…")
        df_raw = pd.read_excel(uploaded)

        cols_map = {c.lower().strip(): c for c in df_raw.columns}

        def find_col(possibles):
            for p in possibles:
                for low, orig in cols_map.items():
                    if p.lower() in low:
                        return orig
            return None

        col_nombre = find_col(["apellidos","nombre","empleado"])
        col_fecha = find_col(["fecha"])
        col_horas = find_col(["tiempo","horas","jornada"])

        if not col_nombre or not col_fecha or not col_horas:
            st.error("El Excel no tiene columnas válidas.")
            st.stop()

        df = pd.DataFrame()
        df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
        df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce").dt.date
        df["horas"] = df_raw[col_horas].apply(time_str_to_hours)
        df = df.dropna(subset=["fecha"])
        df = df[df["nombre"] != ""]

        st.success(f"{len(df)} registros Excel importados.")

    else:
        st.info("Procesando CSV…")
        uploaded.seek(0)
        df_raw = pd.read_csv(uploaded, sep=None, engine="python")

        cols_map = {c.lower().strip(): c for c in df_raw.columns}

        def find_col(possibles):
            for p in possibles:
                for low, orig in cols_map.items():
                    if p.lower() in low:
                        return orig
            return None

        col_nombre = find_col(["apellidos","nombre","empleado"])
        col_fecha = find_col(["fecha"])
        col_horas = find_col(["tiempo","horas","jornada"])

        if not col_nombre or not col_fecha or not col_horas:
            st.error("CSV sin columnas válidas.")
            st.stop()

        df = pd.DataFrame()
        df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
        df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce").dt.date
        df["horas"] = df_raw[col_horas].apply(time_str_to_hours)
        df = df.dropna(subset=["fecha"])
        df = df[df["nombre"] != ""]

        st.success(f"{len(df)} registros CSV importados.")

except Exception as e:
    st.error(f"Error leyendo archivo: {e}")
    st.stop()


# ============================================================
#  TU LÓGICA ORIGINAL DE INFORMES
#  (NO LA MODIFICO — SE INTEGRA DIRECTAMENTE)
# ============================================================

# -----------------
# Detectar mes/año
# -----------------
month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
year = int(df["fecha"].apply(lambda d: d.year).mode()[0])
meses_sp = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
month_name = meses_sp[month-1].capitalize()

folder = create_month_folder_from_date(year, month)
st.info(f"Los informes se guardarán en: {folder}")


# -----------------
# FESTIVOS
# -----------------
st.subheader("📅 Festivos adicionales")
festivos_input = st.text_input("Introduce festivos AA-MM-DD separados por coma")

manual_festivos = []
for token in [t.strip() for t in festivos_input.split(",") if t.strip()]:
    d = safe_parse_date(token)
    if d:
        manual_festivos.append(d)

# Ausencias
if "dias_por_empleado" not in st.session_state:
    st.session_state.dias_por_empleado = {}

st.subheader("🏖️ Registrar ausencias")
emple_sel = st.selectbox("Empleado", sorted(df["nombre"].unique()))
motivo_sel = st.selectbox("Motivo", ["Vacaciones","Permiso","Baja médica"])
rango = st.date_input("Rango fechas", [])

if st.button("Añadir ausencia"):
    if len(rango) == 2:
        desde, hasta = rango
        st.session_state.dias_por_empleado.setdefault(emple_sel,{})
        st.session_state.dias_por_empleado[emple_sel].setdefault(motivo_sel,[])
        st.session_state.dias_por_empleado[emple_sel][motivo_sel].extend(list(daterange(desde,hasta)))
        st.success("Ausencia registrada.")


festivos_objetivos = {safe_parse_date(f) for f in DEFAULT_FESTIVOS if safe_parse_date(f)}
festivos_objetivos |= {safe_parse_date(f) for f in FESTIVOS_ANDALUCIA if safe_parse_date(f)}

for d in manual_festivos:
    festivos_objetivos.add(d)


# ============================================================
#  PROCESADO Y GENERACIÓN DE INFORMES
# ============================================================

if st.button("⚙️ Procesar datos y generar informes"):

    # Agrupar por empleado
    resumen_empleados = []
    for nombre, g in df.groupby("nombre"):
        mapa = {}
        s = g.groupby("fecha")["horas"].sum()
        for d, h in s.items():
            mapa[d] = float(h) if not pd.isna(h) else 0.0
        total_horas = s.sum()
        resumen_empleados.append({
            "nombre": nombre,
            "mapa_horas": mapa,
            "total_horas": float(total_horas)
        })

    dias_mes = list(daterange(date(year,month,1), date(year,month,calendar.monthrange(year,month)[1])))

    global_data = []
    alertas = []

    for r in resumen_empleados:
        nombre = r["nombre"]

        ausencias = list(chain.from_iterable(st.session_state.dias_por_empleado.get(nombre,{}).values())) \
                    if st.session_state.dias_por_empleado.get(nombre) else []

        dias_no_laborables = set(festivos_objetivos).union(set(ausencias))
        dias_laborables = [d for d in dias_mes if d.weekday() < 5 and d not in dias_no_laborables]

        objetivo_mes = len(dias_laborables) * HORAS_LABORALES_DIA
        horas_totales = r["total_horas"]
        diferencia = horas_totales - objetivo_mes
        horas_extra = max(diferencia,0)

        dias_fichados = len([d for d in dias_laborables if d in r["mapa_horas"] and r["mapa_horas"].get(d,0)>0])
        dias_sin = [d for d in dias_laborables if d not in r["mapa_horas"] or r["mapa_horas"].get(d,0)==0]

        global_data.append({
            "Empleado": nombre,
            "Horas Totales": horas_totales,
            "Objetivo Mes": objetivo_mes,
            "Diferencia": diferencia,
            "Horas Extra": horas_extra,
            "Dias Con Fichaje": dias_fichados,
            "Dias Sin Fichaje": len(dias_sin),
            "Fechas Sin Fichar": dias_sin,
            "mapa_horas": r["mapa_horas"],
            "Ausencias": ausencias
        })

        if len(dias_sin) > 0:
            alertas.append((nombre,len(dias_sin),dias_sin))


    # Alerta global
    if alertas:
        st.markdown(
            "<div style='background:#ffdddd;padding:5px;text-align:center;'>⚠️ Empleados con días sin fichaje</div>",
            unsafe_allow_html=True
        )

    # Mostrar resumen rápido
    st.subheader("📊 Resumen Global")
    for r in global_data:
        color = "#f8d7da" if r["Dias Sin Fichaje"]>4 else ("#fff3cd" if r["Dias Sin Fichaje"]>2 else "#e6ffef")
        st.markdown(
            f"<div style='background:{color};padding:8px;border-radius:6px;'>"
            f"<b>{r['Empleado']}</b> — {hours_to_hhmm(r['Horas Totales'])}h / objetivo {hours_to_hhmm(r['Objetivo Mes'])}h — Sin fichar: {r['Dias Sin Fichaje']}"
            f"</div>",
            unsafe_allow_html=True
        )

    # ---------
    # PDF MAKER
    # ---------
    styles = getSampleStyleSheet()

    def pdf_individual(entry, year, month, dias_mes):
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm)

        elems = []

        if logo_path:
            try:
                elems.append(RLImage(logo_path, width=110, height=70))
                elems.append(Spacer(1,8))
            except:
                pass

        encabezado = Table([[f"Empleado: {entry['Empleado']}", f"{month_name} {year}"]],
                           colWidths=[12*cm,6*cm])
        encabezado.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COLOR_SECOND)),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
        ]))
        elems.append(encabezado)
        elems.append(Spacer(1,8))

        resumen_data = [
            ["Total horas", hours_to_hhmm(entry["Horas Totales"])],
            ["Objetivo", hours_to_hhmm(entry["Objetivo Mes"])],
            ["Diferencia", hours_to_hhmm(entry["Diferencia"])],
            ["Horas Extra", hours_to_hhmm(entry["Horas Extra"])],
            ["Días con fichaje", str(entry["Dias Con Fichaje"])],
            ["Días sin fichaje", str(entry["Dias Sin Fichaje"])],
        ]
        t_res = Table(resumen_data, colWidths=[9*cm,6*cm])
        t_res.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.3,colors.grey)]))
        elems.append(t_res)
        elems.append(Spacer(1,8))

        table_data = [["Fecha","Horas","Tipo"]]
        mapa = entry["mapa_horas"]
        aus = entry["Ausencias"]

        for d in dias_mes:
            tipo = "Laborable"
            if d.weekday() >= 5:
                tipo = "Fin de semana"
            if d in festivos_objetivos:
                tipo = "Festivo"

            # si ausencia
            for mot, lista_dias in st.session_state.dias_por_empleado.get(entry["Empleado"],{}).items():
                if d in lista_dias:
                    tipo = mot

            horas = round(mapa.get(d,0),2)
            if tipo=="Laborable" and horas==0:
                tipo="Sin fichar"

            table_data.append([d.strftime("%d/%m/%Y"), hours_to_hhmm(horas), tipo])

        t_days = Table(table_data, colWidths=[6*cm,4*cm,6*cm])
        t_days.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.25,colors.grey),
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COLOR_PRIMARY)),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white)
        ]))
        elems.append(t_days)
        elems.append(Spacer(1,10))

        footer = Paragraph("<para align='center'>Desarrollado por Daniel Gilabert Cantero — Fundación PRODE</para>", styles["Normal"])
        elems.append(footer)

        doc.build(elems)
        bio.seek(0)
        return bio

    def pdf_global(data, year, month_name):
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=landscape(A4))
        elems = []

        if logo_path:
            elems.append(RLImage(logo_path, width=120, height=80))
            elems.append(Spacer(1,6))

        elems.append(Paragraph(f"<b>Resumen Global — {month_name} {year}</b>", styles["Title"]))
        elems.append(Spacer(1,10))

        header = ["Empleado","Horas Tot","Objetivo","Diferencia","Extra","Con fichaje","Sin fichaje"]
        table_data = [header]

        for r in data:
            table_data.append([
                r["Empleado"],
                hours_to_hhmm(r["Horas Totales"]),
                hours_to_hhmm(r["Objetivo Mes"]),
                hours_to_hhmm(r["Diferencia"]),
                hours_to_hhmm(r["Horas Extra"]),
                str(r["Dias Con Fichaje"]),
                str(r["Dias Sin Fichaje"])
            ])

        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#A0C4FF")),
            ('GRID',(0,0),(-1,-1),0.3,colors.grey)
        ]))
        elems.append(t)
        elems.append(Spacer(1,10))

        doc.build(elems)
        bio.seek(0)
        return bio

    # -----------------------
    # GENERAR PDF INDIVIDUAL
    # -----------------------
    uploaded_files = []
    for r in global_data:
        pdf_file = pdf_individual(r, year, month, dias_mes)
        safe_name = r["Empleado"].replace(" ","_").replace("/","_")
        out_path = folder / f"Asistencia_{safe_name}_{year}_{month:02d}.pdf"

        with open(out_path,"wb") as f:
            f.write(pdf_file.getvalue())

        uploaded_files.append((out_path.name, pdf_file))

        st.download_button(
            label=f"📄 Descargar {r['Empleado']}",
            data=pdf_file.getvalue(),
            file_name=out_path.name,
            mime="application/pdf"
        )

    # -----------------------
    # PDF GLOBAL
    # -----------------------
    pdf_g = pdf_global(global_data, year, month_name)
    out_global = folder / f"Resumen_Global_{month_name}_{year}.pdf"
    with open(out_global, "wb") as f:
        f.write(pdf_g.getvalue())

    st.success("Informes generados correctamente.")
    st.download_button(
        label="📘 Descargar Resumen Global",
        data=pdf_g.getvalue(),
        file_name=out_global.name,
        mime="application/pdf"
    )

# ============================================================
st.write("Fin de la app")
# ============================================================

