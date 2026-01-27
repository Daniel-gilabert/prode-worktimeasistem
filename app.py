# app.py
"""
PRODE WorkTimeAsistem — ANALIZADOR AUDITABLE 2026
NO registra fichajes. NO modifica datos de origen.
Analiza Excel / CSV / PDF de terceros para detectar riesgos legales.
"""

import os
import io
import re
import calendar
import hashlib
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =============================
# CONFIGURACIÓN
# =============================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

BASE_DIR = Path(__file__).parent.resolve()
INFORMES_DIR = BASE_DIR / "informes"
INFORMES_DIR.mkdir(exist_ok=True)

# =============================
# HELPERS GENERALES
# =============================
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
    s = str(s).strip().upper()
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m)/60
    h = re.findall(r"(\d+)H", s)
    m = re.findall(r"(\d+)M", s)
    return (int(h[0]) if h else 0) + (int(m[0]) if m else 0)/60

def hours_to_hhmm(h):
    if not h or np.isnan(h):
        return "0:00"
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end-start).days+1):
        yield start + timedelta(n)

# =============================
# TRAZABILIDAD DE ARCHIVOS
# =============================
def calcular_hash_archivo(file_obj):
    file_obj.seek(0)
    h = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return h

# =============================
# AUDITORÍAS 2026
# =============================
def detectar_sobrejornada_diaria(mapa, objetivo):
    return [d for d, h in mapa.items() if h > objetivo]

def detectar_exceso_semanal(mapa, max_sem):
    semanas = {}
    for d, h in mapa.items():
        y, w, _ = d.isocalendar()
        semanas.setdefault((y, w), 0)
        semanas[(y, w)] += h
    return [{"año":y,"semana":w,"horas":h} for (y,w),h in semanas.items() if h > max_sem]

def detectar_jornadas_sin_pausa(mapa, umbral=6):
    return [d for d, h in mapa.items() if h >= umbral]

def registrar_auditoria(periodo, usuario, resumen):
    path = BASE_DIR / "auditorias.csv"
    fila = {
        "fecha": datetime.now().isoformat(sep=" ", timespec="seconds"),
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
# PARSER PDF (sin modificar)
# =============================
def parse_pdf_fichajes(pdf_file):
    registros = []
    empleado = None
    patron = re.compile(r"(\d{2}-\w{3}\.-\d{2}).+?([\dHMS ]+)")
    with pdfplumber.open(pdf_file) as pdf:
        for p in pdf.pages:
            for line in (p.extract_text() or "").split("\n"):
                if line.startswith("Nombre:"):
                    empleado = line.replace("Nombre:", "").strip()
                m = patron.search(line)
                if m and empleado:
                    fecha = pd.to_datetime(m.group(1), dayfirst=True, errors="coerce")
                    horas = time_str_to_hours(m.group(2))
                    if pd.notna(fecha):
                        registros.append({
                            "nombre": empleado,
                            "fecha": fecha.date(),
                            "horas": horas
                        })
    return pd.DataFrame(registros)
# app.py
"""
PRODE WorkTimeAsistem — ANALIZADOR AUDITABLE 2026
NO registra fichajes. NO modifica datos de origen.
Analiza Excel / CSV / PDF de terceros para detectar riesgos legales.
"""

import os
import io
import re
import calendar
import hashlib
from datetime import datetime, timedelta, date
from pathlib import Path
from itertools import chain

import pandas as pd
import numpy as np
import streamlit as st
import pdfplumber

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =============================
# CONFIGURACIÓN
# =============================
APP_NAME = "PRODE WorkTimeAsistem"
ADMIN_KEY = "PRODE-ADMIN-ADMIN"

HORAS_SEMANALES = 38.5
HORAS_LABORALES_DIA = HORAS_SEMANALES / 5

BASE_DIR = Path(__file__).parent.resolve()
INFORMES_DIR = BASE_DIR / "informes"
INFORMES_DIR.mkdir(exist_ok=True)

# =============================
# HELPERS GENERALES
# =============================
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
    s = str(s).strip().upper()
    if ":" in s:
        h, m = s.split(":")
        return int(h) + int(m)/60
    h = re.findall(r"(\d+)H", s)
    m = re.findall(r"(\d+)M", s)
    return (int(h[0]) if h else 0) + (int(m[0]) if m else 0)/60

def hours_to_hhmm(h):
    if not h or np.isnan(h):
        return "0:00"
    m = int(round(h * 60))
    return f"{m//60}:{m%60:02d}"

def daterange(start, end):
    for n in range((end-start).days+1):
        yield start + timedelta(n)

# =============================
# TRAZABILIDAD DE ARCHIVOS
# =============================
def calcular_hash_archivo(file_obj):
    file_obj.seek(0)
    h = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return h

# =============================
# AUDITORÍAS 2026
# =============================
def detectar_sobrejornada_diaria(mapa, objetivo):
    return [d for d, h in mapa.items() if h > objetivo]

def detectar_exceso_semanal(mapa, max_sem):
    semanas = {}
    for d, h in mapa.items():
        y, w, _ = d.isocalendar()
        semanas.setdefault((y, w), 0)
        semanas[(y, w)] += h
    return [{"año":y,"semana":w,"horas":h} for (y,w),h in semanas.items() if h > max_sem]

def detectar_jornadas_sin_pausa(mapa, umbral=6):
    return [d for d, h in mapa.items() if h >= umbral]

def registrar_auditoria(periodo, usuario, resumen):
    path = BASE_DIR / "auditorias.csv"
    fila = {
        "fecha": datetime.now().isoformat(sep=" ", timespec="seconds"),
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
# PARSER PDF (sin modificar)
# =============================
def parse_pdf_fichajes(pdf_file):
    registros = []
    empleado = None
    patron = re.compile(r"(\d{2}-\w{3}\.-\d{2}).+?([\dHMS ]+)")
    with pdfplumber.open(pdf_file) as pdf:
        for p in pdf.pages:
            for line in (p.extract_text() or "").split("\n"):
                if line.startswith("Nombre:"):
                    empleado = line.replace("Nombre:", "").strip()
                m = patron.search(line)
                if m and empleado:
                    fecha = pd.to_datetime(m.group(1), dayfirst=True, errors="coerce")
                    horas = time_str_to_hours(m.group(2))
                    if pd.notna(fecha):
                        registros.append({
                            "nombre": empleado,
                            "fecha": fecha.date(),
                            "horas": horas
                        })
    return pd.DataFrame(registros)

