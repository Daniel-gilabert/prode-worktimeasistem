# =========================================
# PRODE WorkTimeAsistem - FINAL ESTABLE FIX
# =========================================

import io
import zipfile
from datetime import datetime, timedelta, date

import pandas as pd
import streamlit as st

# =========================================
# CONFIG
# =========================================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_DIA = HORAS_SEMANALES / 5  # 7.7

# =========================================
# SESSION STATE (SEGURO)
# =========================================
def init_state():
    defaults = {
        "activated": False,
        "is_admin": False,
        "user_keys": [ADMIN_KEY, "PRODE-ULTIMAMILLA-DGC"],
        "ausencias": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# =========================================
# UI
# =========================================
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"🏢 {APP_NAME}")

with st.expander("ℹ️ Cómo funciona esta herramienta"):
    st.markdown("""
- Subes **Excel REAL**
- Columnas obligatorias:
  - Empleado
  - Fecha
  - Entrada
  - Salida
- Las horas se **calculan matemáticamente**
- No hay OCR
- No hay interpretación
""")

# =========================================
# ACCESO
# =========================================
st.sidebar.header("🔐 Acceso")
key_input = st.sidebar.text_input("Clave", type="password")

if st.sidebar.button("Activar"):
    if key_input in st.session_state.user_keys:
        st.session_state.activated = True
        st.session_state.is_admin = (key_input == ADMIN_KEY)
        st.sidebar.success("Acceso concedido ✅")
    else:
        st.sidebar.error("Clave incorrecta ❌")

if not st.session_state.activated:
    st.stop()

# =========================================
# SUBIR EXCEL
# =========================================
st.subheader("📂 Subir Excel de fichajes")
uploaded = st.file_uploader("Excel (.xlsx)", type=["xlsx"])

if not uploaded:
    st.stop()

raw = pd.read_excel(uploaded)

# =========================================
# DETECTAR COLUMNAS
# =========================================
cols = {c.lower(): c for c in raw.columns}

def find_col(keywords):
    for kw in keywords:
        for c in cols:
            if kw in c:
                return cols[c]
    return None

col_nombre = find_col(["empleado", "nombre"])
col_fecha = find_col(["fecha"])
col_entrada = find_col(["entrada"])
col_salida = find_col(["salida"])

if not all([col_nombre, col_fecha, col_entrada, col_salida]):
    st.error("❌ El Excel debe tener columnas: Empleado, Fecha, Entrada, Salida")
    st.stop()

# =========================================
# NORMALIZAR DATOS
# =========================================
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

st.success(f"✅ Registros cargados: {len(df)}")
st.dataframe(df.head(20))

# =========================================
# PROCESAR
# =========================================
if st.button("⚙️ Procesar datos"):
    with st.spinner("⏳ Calculando horas reales…"):
        resumen = (
            df.groupby("nombre")["horas"]
            .sum()
            .reset_index()
            .sort_values("horas", ascending=False)
        )

    st.success("✅ Procesado finalizado")
    st.dataframe(resumen)

    # ZIP con informes simples (placeholder)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for _, r in resumen.iterrows():
            zf.writestr(
                f"{r['nombre']}.txt",
                f"{r['nombre']} — Total horas: {r['horas']}"
            )

    st.download_button(
        "📦 Descargar ZIP de informes",
        zip_buffer.getvalue(),
        file_name="Informes.zip",
        mime="application/zip"
    )

st.write("🟢 Aplicación estable.")







