# -----------------------------
# ACCESO TEMPORAL POR CLAVE
# -----------------------------
import streamlit as st

DEFAULT_KEYS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-CAPITALHUMANO-ZMGR",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM"
]

ADMIN_KEY = "PRODE-ADMIN-ADMIN"

# Session state
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.current_key = ""
    st.session_state.is_admin = False

st.sidebar.header("🔐 Acceso temporal")
clave = st.sidebar.text_input("Introduce tu clave:", type="password")
if st.sidebar.button("Entrar"):
    if clave in DEFAULT_KEYS:
        st.session_state.activated = True
        st.session_state.current_key = clave
        st.session_state.is_admin = (clave == ADMIN_KEY)
        st.sidebar.success("Acceso concedido")
    else:
        st.sidebar.error("Clave incorrecta")

if not st.session_state.activated:
    st.warning("Introduce una clave válida para utilizar la herramienta.")
    st.stop()
# app.py
"""
PRODE WorkTimeAsistem - Streamlit app
Basada en tu código original (AsistenciaPro) pero integrada en una web
- Login MSAL (Microsoft)
- Generación de PDFs idéntica a tu lógica
- Subida a SharePoint/OneDrive vía Microsoft Graph (si configuras MSAL secrets)
- Panel admin para departamentos / asignaciones
- Usar logo local: /mnt/data/logo-prode.jpg (o assets/logo-prode.jpg en tu repo)
"""

import os
import io
import json
import calendar
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st
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

# -----------------------------
# CONFIG
# -----------------------------
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"
LOGO_FILENAME = "logo-prode.jpg"
# If you're testing locally, keep the absolute path where you uploaded the logo:
LOGO_LOCAL_PATH = "/mnt/data/logo-prode.jpg"  # <= ruta que has subido
# In production, you should place logo in repo under assets/logo-prode.jpg

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

# Colors (from logo)
COLOR_PRIMARY = "#12486C"
COLOR_ACCENT = "#F5BD2D"
COLOR_BG = "#ECF3F9"
COLOR_SECOND = "#2F709F"
COLOR_TEXT = "#062A54"

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# MSAL / Graph settings (set these in Streamlit secrets or env vars)
MSAL_CLIENT_ID = st.secrets.get("MSAL_CLIENT_ID") or os.environ.get("MSAL_CLIENT_ID")
MSAL_TENANT_ID = st.secrets.get("MSAL_TENANT_ID") or os.environ.get("MSAL_TENANT_ID")
MSAL_CLIENT_SECRET = st.secrets.get("MSAL_CLIENT_SECRET") or os.environ.get("MSAL_CLIENT_SECRET")
# Drive/site settings (optional; Graph can discover too)
SHAREPOINT_SITE_ID = st.secrets.get("SHAREPOINT_SITE_ID") or os.environ.get("SHAREPOINT_SITE_ID")
SHAREPOINT_DRIVE_ID = st.secrets.get("SHAREPOINT_DRIVE_ID") or os.environ.get("SHAREPOINT_DRIVE_ID")
SHAREPOINT_ROOT_PATH = st.secrets.get("SHAREPOINT_ROOT_PATH") or os.environ.get("SHAREPOINT_ROOT_PATH", "deploy_AsistAnalyser")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# -----------------------------
# HELPERS (copiados y mantenidos de tu código)
# -----------------------------
def safe_parse_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def time_str_to_hours(s):
    """Accept formats: 'H:M', 'HH:MM', decimal string '7.5', or numeric."""
    if pd.isna(s):
        return np.nan
    if isinstance(s, (int, float, np.floating, np.integer)):
        return float(s)
    s = str(s).strip()
    if not s:
        return np.nan
    # If format like "7:30"
    if ":" in s:
        try:
            parts = s.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h + m / 60.0
        except:
            pass
    # decimal comma?
    s2 = s.replace(",", ".")
    try:
        return float(s2)
    except:
        return np.nan

def hours_to_hhmm(hours):
    """Convert float hours -> 'H:MM' (no padding on hours)."""
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
    base = BASE_DIR
    folder = base / "informes" / f"{mes_nombre} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

# -----------------------------
# MSAL / Graph minimal helpers (graceful if MSAL not configured)
# -----------------------------
def build_msal_app():
    if not MSAL_AVAILABLE or not MSAL_CLIENT_ID or not MSAL_TENANT_ID:
        return None
    authority = f"https://login.microsoftonline.com/{MSAL_TENANT_ID}"
    return msal.ConfidentialClientApplication(
        MSAL_CLIENT_ID, authority=authority,
        client_credential=MSAL_CLIENT_SECRET
    )

def msal_get_token_on_behalf(scopes):
    # This helper is minimal; in production use complete auth code flow
    # For Streamlit Cloud we use auth_code flow skeleton below
    return None

def graph_upload_bytes_to_drive(drive_id, remote_path, token, data_bytes):
    # drive_id: drive id string
    # remote_path: like "/deploy_AsistAnalyser/Dept/2025-11/file.pdf"
    url = f"{GRAPH_BASE}/drives/{drive_id}/root:{remote_path}:/content"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.put(url, headers=headers, data=data_bytes)
    return r

# -----------------------------
# UI - header, auth
# -----------------------------
st.set_page_config(page_title=APP_NAME, layout="wide", page_icon=str(ASSETS_DIR / LOGO_FILENAME) if (ASSETS_DIR / LOGO_FILENAME).exists() else None)
st.markdown(f"<h1 style='color:{COLOR_PRIMARY};'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)

# Show logo - prefer local uploaded path if exists
logo_path_display = None
if Path(LOGO_LOCAL_PATH).exists():
    logo_path_display = LOGO_LOCAL_PATH
elif (ASSETS_DIR / LOGO_FILENAME).exists():
    logo_path_display = str(ASSETS_DIR / LOGO_FILENAME)

if logo_path_display:
    try:
        st.image(logo_path_display, width=160)
    except Exception:
        pass

st.markdown("<h5 style='text-align:center;color:gray;'>Desarrollado por <b>Daniel Gilabert Cantero</b> — Fundación PRODE</h5>", unsafe_allow_html=True)
st.markdown("---")

# Session state defaults
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.current_key = ""
    st.session_state.is_admin = False
if "user_keys" not in st.session_state:
    st.session_state.user_keys = DEFAULT_KEYS.copy()
if "dias_por_empleado" not in st.session_state:
    st.session_state.dias_por_empleado = {}

# Sidebar - activation (keeps mandatory entry as you requested)
st.sidebar.header("🔐 Acceso (obligatorio)")
key_input = st.sidebar.text_input("Introduce tu clave:", type="password")
if st.sidebar.button("Activar"):
    if key_input.strip() in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.current_key = key_input.strip()
        st.session_state.is_admin = (key_input.strip() == ADMIN_KEY)
        st.sidebar.success("Activado ✅")
    else:
        st.sidebar.error("Clave inválida ❌")

# Admin keys management
if st.session_state.is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠 Gestión claves (Admin)")
    nueva = st.sidebar.text_input("Nueva clave")
    if st.sidebar.button("➕ Añadir clave"):
        if nueva and nueva not in st.session_state.user_keys:
            st.session_state.user_keys.append(nueva)
            st.sidebar.success("Clave añadida")
    to_del = st.sidebar.selectbox("Eliminar clave", [k for k in st.session_state.user_keys if k != ADMIN_KEY])
    if st.sidebar.button("🗑️ Eliminar clave"):
        st.session_state.user_keys.remove(to_del)
        st.sidebar.warning(f"Clave {to_del} eliminada")

if not st.session_state.activated:
    st.warning("Activa la aplicación con tu clave para continuar.")
    st.stop()

# -----------------------------
# Main flow: upload + process (tu lógica intacta)
# -----------------------------
st.subheader("📂 Subir archivo de fichajes (.xlsx/.csv)")
uploaded = st.file_uploader("Selecciona el archivo", type=["xlsx", "xls", "csv"])
if not uploaded:
    st.info("Sube tu archivo de fichajes para continuar.")
    st.stop()

# read file
try:
    if str(uploaded.name).lower().endswith((".xls", ".xlsx")):
        df_raw = pd.read_excel(uploaded)
    else:
        uploaded.seek(0)
        df_raw = pd.read_csv(uploaded, sep=None, engine="python")
except Exception as e:
    st.error(f"No se pudo leer el archivo: {e}")
    st.stop()

# normalize column names & find columns (kept your detection logic)
cols_map_lower = {c.lower().strip(): c for c in df_raw.columns}
def find_col(possible_names):
    for p in possible_names:
        for k, orig in cols_map_lower.items():
            if p.lower() in k:
                return orig
    return None

col_nombre = find_col(["apellidos y nombre", "apellidos nombre", "apellido", "nombre", "empleado"])
col_fecha = find_col(["fecha", "date"])
col_horas = find_col(["tiempo trabajado", "tiempo trabajado(hras)", "tiempotrabajado", "horastrabajadas","horas"])

if col_nombre is None or col_fecha is None or col_horas is None:
    st.error("No se detectaron las columnas requeridas. Debe haber columnas similares a: 'Apellidos y Nombre', 'Fecha', 'Tiempo trabajado(Hras)'.\nColumnas encontradas: " + ", ".join(df_raw.columns))
    st.stop()

df = pd.DataFrame()
df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
df["fecha_orig"] = df_raw[col_fecha]
df["fecha"] = pd.to_datetime(df["fecha_orig"], errors="coerce")
if df["fecha"].isna().any():
    df["fecha"] = df["fecha_orig"].apply(lambda x: safe_parse_date(x) if not pd.isna(x) else None)
df = df.dropna(subset=["fecha"])
df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
df["horas"] = df_raw[col_horas].apply(time_str_to_hours)
df = df[~df["nombre"].isin(["", "nan", "None"])]

st.success(f"{len(df)} registros cargados. Empleados únicos: {df['nombre'].nunique()}")

# detect month/year
month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
year = int(df["fecha"].apply(lambda d: d.year).mode()[0])
meses_sp = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
month_name = meses_sp[month-1].capitalize()

# create folder
folder = create_month_folder_from_date(year, month)
st.info(f"Informes se guardarán en: {folder}")

# extra inputs
st.subheader("📅 Festivos adicionales (opcional)")
festivos_input = st.text_input("Fechas festivas (AAAA-MM-DD, separadas por coma). También puedes dejar vacío.")
manual_festivos = []
for token in [t.strip() for t in festivos_input.split(",") if t.strip()]:
    d = safe_parse_date(token)
    if d:
        manual_festivos.append(d)

st.subheader("🏖️ Registrar ausencias por empleado")
empleado_sel = st.selectbox("Empleado", sorted(df["nombre"].unique()))
motivo_sel = st.selectbox("Motivo", ["Vacaciones", "Permiso", "Baja médica"])
rango = st.date_input("Rango de fechas (inicio, fin)", [])
if st.button("➕ Añadir ausencia"):
    if len(rango) == 2:
        desde, hasta = rango
        st.session_state.dias_por_empleado.setdefault(empleado_sel, {})
        st.session_state.dias_por_empleado[empleado_sel].setdefault(motivo_sel, [])
        st.session_state.dias_por_empleado[empleado_sel][motivo_sel].extend(list(daterange(desde, hasta)))
        st.success(f"{motivo_sel} añadida para {empleado_sel} del {desde} al {hasta}")

umbral_alerta = st.sidebar.slider("Umbral días sin fichar (grave)", 1, 10, 3)
aplicar_todos_festivos = st.checkbox("Aplicar los festivos manuales a todos los empleados", value=True)

festivos_objetivos = [safe_parse_date(f) for f in DEFAULT_FESTIVOS if safe_parse_date(f)]
festivos_objetivos += [safe_parse_date(f) for f in FESTIVOS_ANDALUCIA if safe_parse_date(f)]
festivos_objetivos = set([d for d in festivos_objetivos if d])
if manual_festivos:
    for d in manual_festivos:
        if aplicar_todos_festivos:
            festivos_objetivos.add(d)

# Process and generate reports (core logic preserved)
if st.button("⚙️ Procesar datos y generar informes"):
    resumen_empleados = []
    for nombre, g in df.groupby("nombre"):
        mapa = {}
        s = g.groupby("fecha")["horas"].sum()
        for d, h in s.items():
            mapa[d] = float(h) if not pd.isna(h) else 0.0
        total_horas = s.sum()
        resumen_empleados.append({"nombre": nombre, "mapa_horas": mapa, "total_horas": float(total_horas)})

    dias_mes = list(daterange(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])))

    global_data = []
    alertas = []

    for r in resumen_empleados:
        nombre = r["nombre"]
        festivos_personal = set(festivos_objetivos)
        ausencias = list(chain.from_iterable(st.session_state.dias_por_empleado.get(nombre, {}).values())) if st.session_state.dias_por_empleado.get(nombre) else []
        dias_no_laborables = set(festivos_personal).union(set(ausencias))
        dias_laborables = [d for d in dias_mes if d.weekday() < 5 and d not in dias_no_laborables]

        objetivo_mes = len(dias_laborables) * HORAS_LABORALES_DIA
        horas_totales = r["total_horas"]
        diferencia = horas_totales - objetivo_mes
        horas_extra = max(0.0, diferencia)

        dias_fichados = len([d for d in dias_laborables if d in r["mapa_horas"] and (r["mapa_horas"].get(d, 0) > 0)])
        dias_sin_fichar_list = [d for d in dias_laborables if d not in r["mapa_horas"] or r["mapa_horas"].get(d, 0) == 0]
        dias_sin_fichar = len(dias_sin_fichar_list)

        global_data.append({
            "Empleado": nombre,
            "Horas Totales": horas_totales,
            "Objetivo Mes": objetivo_mes,
            "Diferencia": diferencia,
            "Horas Extra": horas_extra,
            "Dias Con Fichaje": dias_fichados,
            "Dias Sin Fichaje": dias_sin_fichar,
            "Fechas Sin Fichar": dias_sin_fichar_list,
            "mapa_horas": r["mapa_horas"],
            "Ausencias": ausencias
        })

        if dias_sin_fichar > 0:
            alertas.append((nombre, dias_sin_fichar, dias_sin_fichar_list))

    if alertas:
        st.markdown("<div style='position:fixed;top:0;left:0;width:100%;background-color:#ffdddd;padding:8px;text-align:center;z-index:9999;'>"
                    "<b>⚠️ ALERTAS DE ASISTENCIA: hay empleados con días sin fichar</b></div>",
                    unsafe_allow_html=True)
        st.write("")

    # UI summary (same style)
    st.subheader("📊 Resumen Global")
    for r in global_data:
        color = "#f8d7da" if r["Dias Sin Fichaje"] > 4 else ("#fff3cd" if r["Dias Sin Fichaje"] > 2 else "#e6ffef")
        st.markdown(
            f"<div style='background:{color};padding:8px;border-radius:6px;margin-bottom:6px;'>"
            f"<b>{r['Empleado']}</b> — Total: {hours_to_hhmm(r['Horas Totales'])} h | Objetivo: {hours_to_hhmm(r['Objetivo Mes'])} h | Sin fichar: {r['Dias Sin Fichaje']} días"
            f"</div>", unsafe_allow_html=True)

    styles = getSampleStyleSheet()

    def generate_pdf_individual(entry, year, month, dias_mes):
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm)
        elems = []

        # Logo
        use_logo = None
        if Path(LOGO_LOCAL_PATH).exists():
            use_logo = LOGO_LOCAL_PATH
        elif (ASSETS_DIR / LOGO_FILENAME).exists():
            use_logo = str(ASSETS_DIR / LOGO_FILENAME)

        if use_logo:
            try:
                elems.append(RLImage(use_logo, width=120, height=80))
                elems.append(Spacer(1, 6))
            except Exception:
                pass

        encabezado = Table([[f"Empleado: {entry['Empleado']}", f"{month_name} {year}"]], colWidths=[12*cm, 6*cm])
        encabezado.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(COLOR_SECOND)),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor(COLOR_TEXT)),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER')
        ]))
        elems.append(encabezado)
        elems.append(Spacer(1, 8))

        resumen_data = [
            ["Total horas mes", f"{hours_to_hhmm(entry['Horas Totales'])} h"],
            ["Objetivo total", f"{hours_to_hhmm(entry['Objetivo Mes'])} h"],
            ["Diferencia", f"{hours_to_hhmm(entry['Diferencia'])} h"],
            ["Horas Extra", f"{hours_to_hhmm(entry['Horas Extra'])} h"],
            ["Días con fichaje", str(entry['Dias Con Fichaje'])],
            ["Días sin fichaje", str(entry['Dias Sin Fichaje'])]
        ]
        t_res = Table(resumen_data, colWidths=[9*cm, 6*cm])
        t_res.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.3,colors.grey),('BACKGROUND',(0,0),(-1,-1),colors.whitesmoke)]))
        elems.append(t_res)
        elems.append(Spacer(1, 8))

        table_data = [["Fecha","Horas","Tipo"]]
        mapa = entry["mapa_horas"]
        for d in dias_mes:
            tipo = "Laborable"
            if d.weekday() >= 5:
                tipo = "Fin de semana"
            if d in festivos_personal:
                tipo = "Festivo"
            for mot, fechas in st.session_state.dias_por_empleado.get(entry['Empleado'], {}).items():
                if d in fechas:
                    tipo = mot
            horas = round(mapa.get(d, 0) or 0, 2)
            if tipo == "Laborable" and horas == 0:
                tipo = "Sin fichar"
            table_data.append([d.strftime("%d/%m/%Y"), hours_to_hhmm(horas), tipo])

        t_days = Table(table_data, colWidths=[6*cm, 4*cm, 6*cm])
        t_days.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.25,colors.grey),
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COLOR_PRIMARY)),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ]))
        elems.append(t_days)
        elems.append(Spacer(1, 8))

        footer = Paragraph("<para align='center'><font color='#555555'><b>Desarrollado por Daniel Gilabert Cantero</b> — Fundación PRODE</font></para>", styles["Normal"])
        elems.append(footer)

        doc.build(elems)
        bio.seek(0)
        return bio

    def generate_pdf_global_report(global_data_list, month_name, year):
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
        elems = []

        use_logo = None
        if Path(LOGO_LOCAL_PATH).exists():
            use_logo = LOGO_LOCAL_PATH
        elif (ASSETS_DIR / LOGO_FILENAME).exists():
            use_logo = str(ASSETS_DIR / LOGO_FILENAME)

        if use_logo:
            try:
                elems.append(RLImage(use_logo, width=140, height=90))
                elems.append(Spacer(1,6))
            except:
                pass

        elems.append(Paragraph(f"<b>Resumen Global de Asistencia — {month_name} {year}</b>", styles["Title"]))
        elems.append(Spacer(1,8))

        header = ["Empleado","Horas Totales","Objetivo","Diferencia","Horas Extra","Días con fichaje","Días sin fichaje"]
        table_data = [header]
        for r in global_data_list:
            table_data.append([
                Paragraph(r["Empleado"], styles["Normal"]),
                hours_to_hhmm(r["Horas Totales"]),
                hours_to_hhmm(r["Objetivo Mes"]),
                hours_to_hhmm(r["Diferencia"]),
                hours_to_hhmm(r["Horas Extra"]),
                str(r["Dias Con Fichaje"]),
                str(r["Dias Sin Fichaje"])
            ])

        col_widths = [6*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#A0C4FF")),
            ('TEXTCOLOR',(0,0),(-1,0),colors.black),
            ('GRID',(0,0),(-1,-1),0.3,colors.grey),
            ('ALIGN',(1,1),(-1,-1),'CENTER'),
            ('FONTSIZE',(0,0),(-1,-1),9),
        ]))

        for i, r in enumerate(global_data_list, start=1):
            if r["Dias Sin Fichaje"] > 4:
                table.setStyle(TableStyle([('BACKGROUND',(0,i),(-1,i),colors.lightcoral)]))
            elif r["Dias Sin Fichaje"] > 2:
                table.setStyle(TableStyle([('BACKGROUND',(0,i),(-1,i),colors.lightyellow)]))

        elems.append(table)
        elems.append(Spacer(1,10))

        total_empleados = len(global_data_list)
        promedio_horas_totales = sum([x["Horas Totales"] for x in global_data_list]) / total_empleados if total_empleados else 0
        promedio_objetivo = sum([x["Objetivo Mes"] for x in global_data_list]) / total_empleados if total_empleados else 0
        promedio_diferencia = sum([x["Diferencia"] for x in global_data_list]) / total_empleados if total_empleados else 0
        total_alertas = sum([1 for x in global_data_list if x["Dias Sin Fichaje"] > 2])

        resumen_table_data = [
            ["Total empleados analizados:", str(total_empleados)],
            ["Promedio horas trabajadas:", hours_to_hhmm(promedio_horas_totales)],
            ["Promedio objetivo:", hours_to_hhmm(promedio_objetivo)],
            ["Promedio diferencia:", hours_to_hhmm(promedio_diferencia)],
            ["Empleados con alertas (≥2 días sin fichar):", str(total_alertas)]
        ]
        rt = Table(resumen_table_data, colWidths=[10*cm, 6*cm])
        rt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),9)]))
        elems.append(Paragraph("<b>Resumen Estadístico</b>", styles["Heading3"]))
        elems.append(rt)
        elems.append(Spacer(1,6))
        elems.append(Paragraph("<para align='center'><font color='#555555'><b>Desarrollado por Daniel Gilabert Cantero</b> — Fundación PRODE</font></para>", styles["Normal"]))

        doc.build(elems)
        bio.seek(0)
        return bio

    # Save individual PDFs and provide downloads + optional upload to SharePoint
    uploaded_files = []
    for r in global_data:
        festivos_personal = set(festivos_objetivos)
        pdf_ind = generate_pdf_individual(r, year, month, dias_mes)
        safe_name = r["Empleado"].replace("/", "_").replace("\\", "_").replace(" ", "_")
        out_path = folder / f"Asistencia_{safe_name}_{year}_{month:02d}.pdf"
        with open(out_path, "wb") as f:
            f.write(pdf_ind.getvalue())
        uploaded_files.append((out_path.name, pdf_ind))

        st.download_button(
            label=f"📄 Descargar {r['Empleado']}",
            data=pdf_ind.getvalue(),
            file_name=out_path.name,
            mime="application/pdf"
        )

    pdf_global = generate_pdf_global_report(global_data, month_name, year)
    out_global = folder / f"Resumen_Global_Asistencia_{month_name}_{year}.pdf"
    with open(out_global, "wb") as f:
        f.write(pdf_global.getvalue())

    st.success(f"✅ Informes generados y guardados en: {folder}")
    st.download_button(
        label="📘 Descargar Resumen Global",
        data=pdf_global.getvalue(),
        file_name=out_global.name,
        mime="application/pdf"
    )

    # Optional: upload to SharePoint if token and drive id available
    if MSAL_AVAILABLE and st.session_state.get("token") and SHAREPOINT_DRIVE_ID:
        token = st.session_state.get("token")
        for fname, pdf in uploaded_files:
            dept = st.session_state.get("current_dept", "General")
            remote_path = f"/{SHAREPOINT_ROOT_PATH}/{dept}/{year}-{month:02d}/{fname}"
            r = graph_upload_bytes_to_drive(SHAREPOINT_DRIVE_ID, remote_path, token, pdf.getvalue())
            if r is not None and r.status_code in (200,201):
                st.info(f"Subido a SharePoint: {remote_path}")
            else:
                st.error(f"Error subiendo {fname} a SharePoint (ver logs)")

st.write("Fin de la app")

