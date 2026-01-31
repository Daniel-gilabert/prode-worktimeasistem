# app.py
"""
PRODE WorkTimeAsistem - Streamlit app (FINAL)
- Lee: Excel (.xls/.xlsx), CSV (Informe de Control de Presencia)
- Calcula objetivo mensual, diferencia y horas extra (misma lógica)
- Genera PDFs individuales y globales con coloreado profesional
- Activación por clave, gestión de ausencias y festivos
- Autor: preparado para AMCHÍ / Fundación PRODE
"""

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

# -----------------------------
# CONFIG
# -----------------------------
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"
LOGO_FILENAME = "logo-prode.jpg"
LOGO_LOCAL_PATH = "/mnt/data/logo-prode.jpg"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5  # 7.7

DEFAULT_KEYS = [
    "PRODE-ADMIN-ADMIN",
    "PRODE-ULTIMAMILLA-DGC",
    "PRODE-ULTIMAMILLA-JLM",
    "PRODE-CAPITALHUMANO-ZMGR"
]
from datetime import datetime, timedelta, date

CURRENT_YEAR = datetime.now().year

DEFAULT_FESTIVOS = [
    f"{CURRENT_YEAR}-01-01",  # Año Nuevo
    f"{CURRENT_YEAR}-01-06",  # Reyes
    f"{CURRENT_YEAR}-05-01",  # Día del Trabajo
    f"{CURRENT_YEAR}-08-15",  # Asunción
    f"{CURRENT_YEAR}-10-12",  # Fiesta Nacional
    f"{CURRENT_YEAR}-11-01",  # Todos los Santos
    f"{CURRENT_YEAR}-12-06",  # Constitución
    f"{CURRENT_YEAR}-12-08",  # Inmaculada
    f"{CURRENT_YEAR}-12-25",  # Navidad
]

FESTIVOS_ANDALUCIA = [
    f"{CURRENT_YEAR}-02-28"
]




# COLORES acordados (puedes cambiarlos si quieres)
COLOR_HORA_EXTRA = "#d8fcd8"     # verde suave
COLOR_DEFICIT = "#ffe4b2"        # naranja suave
COLOR_SIN_MODERADO = "#fff6a3"   # amarillo suave
COLOR_SIN_GRAVE = "#ffb3b3"      # rojo claro
COLOR_FESTIVO = "#cfe3ff"        # azul suave
COLOR_VACACIONES = "#e4ceff"     # morado suave
COLOR_PERMISO = "#ffd6f3"        # rosa suave
COLOR_BAJA = "#c9f2e7"           # verde azulado
COLOR_NORMAL = "#ffffff"         # blanco / sin resaltado
COLOR_ROW_ALT = "#f7f7f7"        # gris claro para fondo opcional

COLOR_PRIMARY = "#12486C"
COLOR_SECOND = "#2F709F"
COLOR_TEXT = "#062A54"

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# -----------------------------
# HELPERS
# -----------------------------
def safe_parse_date(x):
    try:
        return pd.to_datetime(x).date()
    except:
        return None

def time_str_to_hours(s):
    """Accept 'H:M', 'HH:MM', '7.5', '7H 30M', etc."""
    if pd.isna(s):
        return np.nan
    if isinstance(s, (int, float, np.floating, np.integer)):
        return float(s)
    s = str(s).strip()
    if not s:
        return np.nan
    # Format H:MM
    if ":" in s:
        try:
            parts = s.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h + m/60.0
        except:
            pass
    # Format like "7H 30M"
    if "H" in s.upper():
        try:
            H = re.findall(r"(\d+)\s*H", s.upper())
            M = re.findall(r"(\d+)\s*M", s.upper())
            h = int(H[0]) if H else 0
            m = int(M[0]) if M else 0
            return h + m/60.0
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
    folder = BASE_DIR / "informes" / f"{mes_nombre} {year}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder



# -----------------------------
# STREAMLIT UI - CABECERA
# -----------------------------
st.set_page_config(page_title=APP_NAME, layout="wide")
st.markdown(f"<h1 style='color:{COLOR_PRIMARY};'>🏢 {APP_NAME}</h1>", unsafe_allow_html=True)

logo_path_display = None
if Path(LOGO_LOCAL_PATH).exists():
    logo_path_display = LOGO_LOCAL_PATH
elif (ASSETS_DIR / LOGO_FILENAME).exists():
    logo_path_display = str(ASSETS_DIR / LOGO_FILENAME)

if logo_path_display:
    try:
        st.image(logo_path_display, width=160)
    except:
        pass

st.markdown("<h5 style='text-align:center;color:gray;'>Desarrollado por <b>Daniel Gilabert Cantero</b> — Fundación PRODE</h5>", unsafe_allow_html=True)
st.markdown("---")

# -----------------------------
# Session defaults & auth
# -----------------------------
if "activated" not in st.session_state:
    st.session_state.activated = False
    st.session_state.current_key = ""
    st.session_state.is_admin = False
if "user_keys" not in st.session_state:
    st.session_state.user_keys = DEFAULT_KEYS.copy()
if "dias_por_empleado" not in st.session_state:
    st.session_state.dias_por_empleado = {}

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
# Upload file
# -----------------------------
st.subheader("📂 Subir archivo de fichajes (.xlsx/.csv)")
uploaded = st.file_uploader("Selecciona el archivo", type=["xlsx", "xls", "csv"])
if not uploaded:
    st.info("Sube tu archivo de fichajes para continuar.")
    st.stop()

# -----------------------------
# Read file ( Excel / CSV)
# -----------------------------
try:
    if str(uploaded.name).lower().endswith(".pdf"):
        st.info("Procesando PDF…")
        df = parse_pdf_fichajes(uploaded)
        if df.empty:
            st.error("No se extrajeron registros del PDF.")
            st.stop()
        st.success(f"{len(df)} registros PDF importados. Empleados: {df['nombre'].nunique()}")
        # normalizar nombres de columna
        df = df.rename(columns={"nombre":"nombre","fecha":"fecha","horas":"horas"})
    elif str(uploaded.name).lower().endswith((".xls", ".xlsx")):
        st.info("Procesando Excel…")
        df_raw = pd.read_excel(uploaded)
        cols_map_lower = {c.lower().strip(): c for c in df_raw.columns}
        def find_col(possible_names):
            for p in possible_names:
                for k, orig in cols_map_lower.items():
                    if p.lower() in k:
                        return orig
            return None
        col_nombre = find_col(["apellidos y nombre", "apellidos nombre", "apellido", "nombre", "empleado"])
        col_fecha = find_col(["fecha", "date"])
        col_horas = find_col(["tiempo trabajado", "tiempo trabajado(hras)", "tiempotrabajado", "horastrabajadas","horas","jornada"])
        if col_nombre is None or col_fecha is None or col_horas is None:
            st.error("No se detectaron las columnas requeridas en el Excel/CSV.")
            st.error("Columnas encontradas: " + ", ".join(df_raw.columns))
            st.stop()
        df = pd.DataFrame()
        df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
        df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce")
        if df["fecha"].isna().any():
            df["fecha"] = df["fecha"].apply(lambda x: safe_parse_date(x) if not pd.isna(x) else None)
        df = df.dropna(subset=["fecha"])
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
        df["horas"] = df_raw[col_horas].apply(time_str_to_hours)
        df = df[~df["nombre"].isin(["", "nan", "None"])]
        st.success(f"{len(df)} registros Excel importados. Empleados: {df['nombre'].nunique()}")
    else:
        st.info("Procesando CSV…")
        uploaded.seek(0)
        df_raw = pd.read_csv(uploaded, sep=None, engine="python")
        cols_map_lower = {c.lower().strip(): c for c in df_raw.columns}
        def find_col(possible_names):
            for p in possible_names:
                for k, orig in cols_map_lower.items():
                    if p.lower() in k:
                        return orig
            return None
        col_nombre = find_col(["apellidos", "nombre", "empleado"])
        col_fecha = find_col(["fecha", "date"])
        col_horas = find_col(["tiempo trabajado", "horas", "jornada"])
        if col_nombre is None or col_fecha is None or col_horas is None:
            st.error("No se detectaron columnas válidas en el CSV.")
            st.stop()
        df = pd.DataFrame()
        df["nombre"] = df_raw[col_nombre].astype(str).str.strip()
        df["fecha"] = pd.to_datetime(df_raw[col_fecha], errors="coerce")
        if df["fecha"].isna().any():
            df["fecha"] = df["fecha"].apply(lambda x: safe_parse_date(x) if not pd.isna(x) else None)
        df = df.dropna(subset=["fecha"])
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
        df["horas"] = df_raw[col_horas].apply(time_str_to_hours)
        df = df[~df["nombre"].isin(["", "nan", "None"])]
        st.success(f"{len(df)} registros CSV importados. Empleados: {df['nombre'].nunique()}")

except Exception as e:
    st.error(f"No se pudo leer el archivo: {e}")
    st.stop()

# -----------------------------
# Detect month/year
# -----------------------------
month = int(df["fecha"].apply(lambda d: d.month).mode()[0])
year = int(df["fecha"].apply(lambda d: d.year).mode()[0])
meses_sp = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
month_name = meses_sp[month-1].capitalize()



# -----------------------------
# Festivos manuales y ausencias
# -----------------------------

# ===== FESTIVOS ADICIONALES =====
st.subheader("📅 Festivos adicionales (opcional)")

empleado_festivos = st.selectbox(
    "Empleado",
    sorted(df["nombre"].unique()),
    key="empleado_festivos"
)

festivos_input = st.text_input(
    "Fechas festivas (AAAA-MM-DD, separadas por coma). Dejar vacío si no hay.",
    key="festivos_input_por_empleado"
)

aplicar_festivos_a_todos = st.checkbox(
    "Aplicar los festivos manuales a todos los empleados",
    value=True,
    key="festivos_todos"
)
if st.button("➕ Añadir festivos"):
    manual_festivos = []
    for token in [t.strip() for t in festivos_input.split(",") if t.strip()]:
        d = safe_parse_date(token)
        if d:
            manual_festivos.append(d)

    if manual_festivos:
        if aplicar_festivos_a_todos:
            for d in manual_festivos:
                festivos_objetivos.add(d)
            st.success("Festivos añadidos a todos los empleados")
        else:
            st.session_state.dias_por_empleado.setdefault(empleado_festivos, {})
            st.session_state.dias_por_empleado[empleado_festivos].setdefault("Festivo", [])
            st.session_state.dias_por_empleado[empleado_festivos]["Festivo"].extend(manual_festivos)
            st.success(f"Festivos añadidos a {empleado_festivos}")
manual_festivos = []
for token in [t.strip() for t in festivos_input.split(",") if t.strip()]:
    d = safe_parse_date(token)
    if d:
        manual_festivos.append(d)

# Guardar festivos SOLO por empleado (si NO es global)
if manual_festivos and not aplicar_festivos_a_todos:
    st.session_state.dias_por_empleado.setdefault(empleado_festivos, {})
    st.session_state.dias_por_empleado[empleado_festivos].setdefault("Festivo", [])
    st.session_state.dias_por_empleado[empleado_festivos]["Festivo"].extend(manual_festivos)


st.subheader("🏖️ Registrar ausencias por empleado")
empleado_ausencia = st.selectbox(
    "Empleado",
    sorted(df["nombre"].unique()),
    key="empleado_ausencias"
)

motivo_sel = st.selectbox("Motivo", ["Vacaciones", "Permiso", "Baja médica"])
rango = st.date_input("Rango de fechas (inicio, fin)", [])
if st.button("➕ Añadir ausencia"):
    if len(rango) == 2:
        desde, hasta = rango
        st.session_state.dias_por_empleado.setdefault(empleado_ausencia, {})

        st.session_state.dias_por_empleado[empleado_ausencia].setdefault(motivo_sel, [])

        st.session_state.dias_por_empleado[empleado_ausencia][motivo_sel].extend(...)

        st.success(f"{motivo_sel} añadida para {empleado_sel} del {desde} al {hasta}")

umbral_alerta = st.sidebar.slider("Umbral días sin fichar (grave)", 1, 10, 3)
aplicar_todos_festivos = st.checkbox("Aplicar los festivos manuales a todos los empleados", value=True)

festivos_objetivos = {safe_parse_date(f) for f in DEFAULT_FESTIVOS if safe_parse_date(f)}
festivos_objetivos |= {safe_parse_date(f) for f in FESTIVOS_ANDALUCIA if safe_parse_date(f)}
if manual_festivos:
    if aplicar_todos_festivos:
        for d in manual_festivos:
            festivos_objetivos.add(d)

# -----------------------------
# Procesado y generación de datos globales
# -----------------------------
if st.button("⚙️ Procesar datos y generar informes"):
    folder = create_month_folder_from_date(year, month)

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
        dias_laborables = [
            d for d in dias_mes
            if (
                d.weekday() < 5
                and (
                    d not in festivos_personal
                    or d in r["mapa_horas"]  # ← SI SE FICHA EN FESTIVO, CUENTA
                )
                and d not in ausencias
            )
        ]




        objetivo_mes = len(dias_laborables) * HORAS_LABORALES_DIA
        horas_totales = r["total_horas"]
        diferencia = horas_totales - objetivo_mes
        horas_extra = max(0.0, diferencia)

        dias_fichados = len([d for d in dias_laborables if d in r["mapa_horas"] and (r["mapa_horas"].get(d, 0) > 0)])
        dias_sin_fichar_list = [d for d in dias_laborables if d not in r["mapa_horas"] or r["mapa_horas"].get(d, 0) == 0]
        dias_sin_fichar_list = [
       d for d in dias_laborables
         if d not in festivos_personal
         and (d not in r["mapa_horas"] or r["mapa_horas"].get(d, 0) == 0)
     ]
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

    # -----------------------------
    # UI - Resumen Global
    # -----------------------------
    st.subheader("📊 Resumen Global")

    for r in global_data:
        color = "#f8d7da" if r["Dias Sin Fichaje"] > 4 else (
            "#fff3cd" if r["Dias Sin Fichaje"] > 2 else "#e6ffef"
        )

        col1, col2 = st.columns([6, 1])

        with col1:
            st.markdown(
                f"<div style='background:{color};padding:8px;border-radius:6px;'>"
                f"<b>{r['Empleado']}</b> — "
                f"Total: {hours_to_hhmm(r['Horas Totales'])} h | "
                f"Objetivo: {hours_to_hhmm(r['Objetivo Mes'])} h | "
                f"Sin fichar: {r['Dias Sin Fichaje']} días"
                f"</div>",
                unsafe_allow_html=True
            )

        with col2:
            safe_name = r["Empleado"].replace("/", "_").replace("\\", "_").replace(" ", "_")
            pdf_name = f"Asistencia_{safe_name}_{year}_{month:02d}.pdf"
            pdf_path = folder / pdf_name

            if pdf_path.exists():
                st.download_button(
                    label="⬇",
                    data=pdf_path.read_bytes(),
                    file_name=pdf_name,
                    mime="application/pdf",
                    key=f"btn_{safe_name}"
                )



    # -----------------------------
    # PDF Individual (con coloreado diario)
    # -----------------------------
    def generate_pdf_individual(entry, year, month, dias_mes):
        styles = getSampleStyleSheet()

        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm)
        elems = []

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
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
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

        # Tabla por días (con coloreado por fila según prioridad)
        table_data = [["Fecha","Horas","Tipo"]]
        mapa = entry["mapa_horas"]
        ausencias = entry.get("Ausencias", [])
for d in dias_mes:
    tipo = "Laborable"

    if d.weekday() >= 5:
        tipo = "Fin de semana"

    if d in festivos_objetivos:
        tipo = "Festivo"

    # Ausencias concretas
    for mot, fechas in st.session_state.dias_por_empleado.get(entry["Empleado"], {}).items():
        if d in fechas:
            tipo = mot

    horas = round(mapa.get(d, 0) or 0, 2)

    if tipo == "Laborable" and horas == 0:
        tipo = "Sin fichar"

    table_data.append([
        d.strftime("%d/%m/%Y"),
        hours_to_hhmm(horas),
        tipo
    ])
t_days = Table(table_data, colWidths=[6*cm, 4*cm, 6*cm], repeatRows=1)

t_days.setStyle(TableStyle([
    ('GRID',(0,0),(-1,-1),0.25,colors.grey),
    ('BACKGROUND',(0,0),(-1,0),colors.HexColor(COLOR_PRIMARY)),
    ('TEXTCOLOR',(0,0),(-1,0),colors.white),
    ('FONTSIZE',(0,0),(-1,-1),9),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
]))

        # Aplicar coloreado por fila (prioridad):
        # 1. Ausencia (Vacaciones / Permiso / Baja) -> colores específicos
        # 2. Festivo -> azul
        # 3. Fin de semana -> gris claro (no resaltado)
        # 4. Sin fichar -> rojo/amarillo según gravedad (a nivel diario lo marcamos rojo)
        # 5. Horas > HORAS_LABORALES_DIA -> verde (extra)
        # 6. Horas < HORAS_LABORALES_DIA -> naranja (déficit)
for i_row in range(1, len(table_data)):
row = table_data[i_row]
fecha_str = row[0]
tipo = row[2]
horas_str = row[1]
# parse fecha back
try:
    dd = datetime.strptime(fecha_str, "%d/%m/%Y").date()
except:
    dd = None

# default
row_color = colors.whitesmoke

if tipo in ("Vacaciones", "Permiso", "Baja médica"):
    if tipo == "Vacaciones":
        row_color = colors.HexColor(COLOR_VACACIONES)
    elif tipo == "Permiso":
        row_color = colors.HexColor(COLOR_PERMISO)
    else:
        row_color = colors.HexColor(COLOR_BAJA)
elif dd and dd in festivos_objetivos:
    row_color = colors.HexColor(COLOR_FESTIVO)
elif dd and dd.weekday() >= 5:
    row_color = colors.HexColor("#f0f4f7")  # weekend light
else:
    # horas num
    try:
        h = 0.0
        # convert hh:mm string
        if ":" in horas_str:
            p = horas_str.split(":")
            h = int(p[0]) + int(p[1])/60.0
        else:
            h = float(horas_str)
    except:
        h = 0.0

    if tipo == "Sin fichar":
        row_color = colors.HexColor(COLOR_SIN_GRAVE)
    elif h > HORAS_LABORALES_DIA:
        row_color = colors.HexColor(COLOR_HORA_EXTRA)
    elif h < HORAS_LABORALES_DIA:
        row_color = colors.HexColor(COLOR_DEFICIT)
    else:
        row_color = colors.whitesmoke

t_days.setStyle(TableStyle([('BACKGROUND',(0,i_row),(-1,i_row),row_color)]))

elems.append(t_days)
    elems.append(Spacer(1, 8))

        # Leyenda individual
        leyenda = [
            ["Leyenda:", "Horario objetivo diario: " + hours_to_hhmm(HORAS_LABORALES_DIA)],
            ["Color extra", "Horas Extra (> objetivo)"],
            ["Color déficit", "Horas < objetivo"],
            ["Color sin fichar", "Sin fichar / ausencia de registro"],
            ["Color festivo", "Festivo"],
            ["Colores ausencias", "Vacaciones / Permiso / Baja médica"]
        ]
        l_tab = Table(leyenda, colWidths=[6*cm, 10*cm])
        l_tab.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.25,colors.lightgrey),
            ('BACKGROUND',(0,1),(0,1),colors.HexColor(COLOR_HORA_EXTRA)),
            ('BACKGROUND',(0,2),(0,2),colors.HexColor(COLOR_DEFICIT)),
            ('BACKGROUND',(0,3),(0,3),colors.HexColor(COLOR_SIN_GRAVE)),
            ('BACKGROUND',(0,4),(0,4),colors.HexColor(COLOR_FESTIVO)),
            ('BACKGROUND',(0,5),(0,5),colors.HexColor(COLOR_VACACIONES)),
            ('FONTSIZE',(0,0),(-1,-1),8)
        ]))
        elems.append(l_tab)
        elems.append(Spacer(1,8))

        footer = Paragraph("<para align='center'><font color='#555555'><b>Desarrollado por Daniel Gilabert Cantero</b> — Fundación PRODE</font></para>", styles["Normal"])
        elems.append(footer)

        doc.build(elems)
        bio.seek(0)
        return bio

    # -----------------------------
    # PDF GLOBAL (coloreado por empleado)
    # -----------------------------
    def generate_pdf_global_report(global_data_list, month_name, year):
        bio = io.BytesIO()
        doc = SimpleDocTemplate(bio, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
        elems = []
        styles = getSampleStyleSheet()

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

        # Leyenda
        leyenda_data = [
            ["Leyenda:", "Sin incidencias (≤2 días sin fichar)", "Atención (3-4 días sin fichar)", "Crítico (>4 días sin fichar)"],
            ["Color:", "", "", ""]
        ]
        leyenda_table = Table(leyenda_data, colWidths=[5*cm, 6*cm, 6*cm, 6*cm])
        leyenda_table.setStyle(TableStyle([
            ('SPAN',(0,0),(0,1)),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('BACKGROUND',(1,1),(1,1),colors.whitesmoke),
            ('BACKGROUND',(2,1),(2,1),colors.HexColor(COLOR_SIN_MODERADO)),
            ('BACKGROUND',(3,1),(3,1),colors.HexColor(COLOR_SIN_GRAVE)),
            ('GRID',(0,0),(-1,-1),0.25,colors.grey),
            ('FONTSIZE',(0,0),(-1,-1),9)
        ]))
        elems.append(leyenda_table)
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

        col_widths = [6*cm, 2.8*cm, 2.8*cm, 2.8*cm, 2.8*cm, 2.8*cm, 2.8*cm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Estilos base
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#A0C4FF")),
            ('TEXTCOLOR',(0,0),(-1,0),colors.black),
            ('GRID',(0,0),(-1,-1),0.3,colors.grey),
            ('ALIGN',(1,1),(-1,-1),'CENTER'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))

        # Aplicar colores por fila según prioridad:
        # 1) Sin fichar grave (>4 días) -> rojo
        # 2) Sin fichar moderado (3-4 días) -> amarillo
        # 3) Horas extra -> verde
        # 4) Déficit -> naranja
        # 5) Normal -> blanco / gris claro
        for i, r in enumerate(global_data_list, start=1):
            dias_sin = r.get("Dias Sin Fichaje", 0)
            diferencia = r.get("Diferencia", 0)
            horas_extra = r.get("Horas Extra", 0)

            if dias_sin > 4:
                row_color = colors.HexColor(COLOR_SIN_GRAVE)
            elif dias_sin > 2:
                row_color = colors.HexColor(COLOR_SIN_MODERADO)
            elif horas_extra > 0:
                row_color = colors.HexColor(COLOR_HORA_EXTRA)
            elif diferencia < 0:
                row_color = colors.HexColor(COLOR_DEFICIT)
            else:
                row_color = colors.whitesmoke

            table.setStyle(TableStyle([('BACKGROUND',(0,i),(-1,i),row_color)]))

        elems.append(table)
        elems.append(Spacer(1,10))

        # Resumen estadístico
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
            ["Empleados con alertas (≥3 días sin fichar):", str(total_alertas)]
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

    # -----------------------------
    # Guardar y ofrecer descargas
    # -----------------------------
    folder = create_month_folder_from_date(year, month)

 

    pdf_global = generate_pdf_global_report(global_data, month_name, year)
    out_global = folder / f"Resumen_Global_Asistencia_{month_name}_{year}.pdf"
    with open(out_global, "wb") as f:
        f.write(pdf_global.getvalue())

    
    st.download_button(
        label="📘 Descargar Resumen Global",
        data=pdf_global.getvalue(),
        file_name=out_global.name,
        mime="application/pdf"
    )

st.write("Fin de la app")









































