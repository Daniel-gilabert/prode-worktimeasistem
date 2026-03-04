"""
Script de carga del organigrama PRODE a Supabase.
Lee organigrama_prode_procesado.xlsx y actualiza la tabla empleados.

Estrategia:
  - Si el correo ya existe en Supabase -> UPDATE (nombre, rol, departamento)
  - Si no existe -> INSERT nuevo empleado
  - responsable_id se resuelve en una segunda pasada

Uso:
  python _fix_organigrama.py            <- aplica cambios reales
  python _fix_organigrama.py --dry-run  <- solo muestra, sin tocar la BD
"""

import os
import sys
import pathlib
import uuid
import unicodedata

# ── Cargar .env ──────────────────────────────────────────────────────────────
base = pathlib.Path(__file__).resolve().parent
for nombre in (".env", "1.env", "1.env.txt"):
    candidato = base / nombre
    if candidato.exists():
        with open(candidato, encoding="utf-8-sig") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, _, valor = linea.partition("=")
                clave = clave.strip()
                valor = valor.strip().strip('"').strip("'")
                if clave and clave not in os.environ:
                    os.environ[clave] = valor
        break

import pandas as pd
from supabase import create_client

DRY_RUN = "--dry-run" in sys.argv

EXCEL_PATH = r"C:\Users\ADMON121_\Downloads\organigrama_prode_procesado.xlsx"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

print(f"\n{'='*60}")
print(f"  WorkTimeAsistem PRODE — Carga de organigrama")
print(f"  Modo: {'DRY-RUN (sin cambios reales)' if DRY_RUN else 'REAL — escribiendo en Supabase'}")
print(f"{'='*60}\n")

# ── Leer Excel ───────────────────────────────────────────────────────────────
df = pd.read_excel(EXCEL_PATH, sheet_name="Organigrama")
df = df.fillna("")
df.columns = [c.strip() for c in df.columns]
print(f"Excel leido: {len(df)} empleados")

# ── Conectar Supabase ─────────────────────────────────────────────────────────
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Obtener empleados actuales en BD ─────────────────────────────────────────
print("Leyendo empleados actuales en Supabase...")
resp = sb.table("empleados").select("id,email,apellidos_y_nombre,rol,departamento").execute()
bd_por_email = {r["email"].strip().lower(): r for r in resp.data if r.get("email")}
print(f"  {len(bd_por_email)} empleados en BD actualmente\n")

# ── PASADA 1: insertar/actualizar empleados (sin responsable_id aun) ──────────
email_a_id: dict[str, str] = {}

nuevos     = 0
actualizados = 0
errores    = 0

for _, row in df.iterrows():
    email     = str(row.get("correo", "")).strip().lower()
    nombre    = str(row.get("nombre_completo", "")).strip()
    rol       = str(row.get("rol", "empleado")).strip().lower()
    depto     = str(row.get("departamento", "")).strip()

    if not email or not nombre:
        continue

    es_responsable = rol in ("responsable", "coordinador")
    es_admin       = rol in ("administrador", "superadministrador")

    if email in bd_por_email:
        emp_id = bd_por_email[email]["id"]
        email_a_id[email] = emp_id
        payload = {
            "apellidos_y_nombre": nombre,
            "rol":                rol,
            "departamento":       depto,
            "es_responsable":     es_responsable,
            "es_admin":           es_admin,
            "activo":             True,
        }
        if not DRY_RUN:
            try:
                sb.table("empleados").update(payload).eq("id", emp_id).execute()
                actualizados += 1
            except Exception as e:
                print(f"  ERROR update {nombre} ({email}): {e}")
                errores += 1
        else:
            actualizados += 1
    else:
        emp_id = str(uuid.uuid4())
        email_a_id[email] = emp_id
        payload = {
            "id":                 emp_id,
            "apellidos_y_nombre": nombre,
            "email":              email,
            "activo":             True,
            "es_responsable":     es_responsable,
            "es_admin":           es_admin,
            "jornada_semanal":    38.5,
            "rol":                rol,
            "departamento":       depto,
            "responsable_id":     None,
        }
        if not DRY_RUN:
            try:
                sb.table("empleados").insert(payload).execute()
                nuevos += 1
            except Exception as e:
                print(f"  ERROR insert {nombre} ({email}): {e}")
                errores += 1
        else:
            nuevos += 1

print(f"Pasada 1 completada:")
print(f"  Nuevos:       {nuevos}")
print(f"  Actualizados: {actualizados}")
print(f"  Errores:      {errores}")

# ── PASADA 2: enlazar responsable_id ─────────────────────────────────────────
print("\nPasada 2 — enlazando responsables...")

def _norm(txt: str) -> str:
    if not txt:
        return ""
    txt = unicodedata.normalize("NFD", txt)
    txt = txt.encode("ascii", "ignore").decode("utf-8")
    return " ".join(txt.strip().upper().split())

# Mapa nombre normalizado → email
nombre_a_email: dict[str, str] = {}
for _, row in df.iterrows():
    nombre = str(row.get("nombre_completo", "")).strip()
    email  = str(row.get("correo", "")).strip().lower()
    if nombre and email:
        nombre_a_email[_norm(nombre)] = email

# Enriquecer con datos actuales de BD
resp2 = sb.table("empleados").select("id,email,apellidos_y_nombre").execute()
for r in resp2.data:
    if r.get("email") and r.get("apellidos_y_nombre"):
        nombre_a_email[_norm(r["apellidos_y_nombre"])] = r["email"].strip().lower()

enlazados     = 0
sin_responsable = 0

for _, row in df.iterrows():
    email      = str(row.get("correo", "")).strip().lower()
    resp_nombre = str(row.get("responsable_directo", "")).strip()

    if not email or not resp_nombre:
        sin_responsable += 1
        continue

    emp_id = email_a_id.get(email)
    if not emp_id:
        continue

    resp_email = nombre_a_email.get(_norm(resp_nombre))
    resp_id    = email_a_id.get(resp_email) if resp_email else None

    if resp_id and resp_id != emp_id:
        if not DRY_RUN:
            try:
                sb.table("empleados").update({"responsable_id": resp_id}).eq("id", emp_id).execute()
                enlazados += 1
            except Exception as e:
                print(f"  ERROR enlazando responsable de {email}: {e}")
        else:
            enlazados += 1
    else:
        sin_responsable += 1

print(f"  Responsables enlazados:          {enlazados}")
print(f"  Sin responsable / no encontrado: {sin_responsable}")

# ── RESUMEN FINAL ─────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  RESUMEN FINAL")
print(f"{'='*60}")
print(f"  Empleados en Excel:         {len(df)}")
print(f"  Nuevos insertados:          {nuevos}")
print(f"  Actualizados:               {actualizados}")
print(f"  Responsables enlazados:     {enlazados}")
print(f"  Errores:                    {errores}")
if DRY_RUN:
    print(f"\n  [DRY-RUN] Ningun cambio aplicado.")
    print(f"  Quita --dry-run para aplicar los cambios reales.")
else:
    print(f"\n  Organigrama cargado correctamente en Supabase.")
print(f"{'='*60}\n")
