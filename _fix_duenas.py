"""
Propaga el departamento del responsable a todos sus empleados en Supabase.
Cada empleado hereda el departamento de su responsable directo.
Los responsables sin jefe (cabezas de jerarquia) conservan su propio departamento.

Uso:
  python _fix_duenas.py [--dry-run]
"""

import os
import sys
import pathlib

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
                if clave.strip() not in os.environ:
                    os.environ[clave.strip()] = valor.strip().strip('"').strip("'")
        break

from supabase import create_client

DRY_RUN = "--dry-run" in sys.argv

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

print(f"\n{'='*60}")
print(f"  Propagar departamento desde responsable a empleados")
print(f"  Modo: {'DRY-RUN' if DRY_RUN else 'REAL'}")
print(f"{'='*60}\n")

# ── Cargar todos los empleados ────────────────────────────────────────────────
resp = sb.table("empleados").select("id,apellidos_y_nombre,email,rol,departamento,responsable_id").execute()
todos = {r["id"]: r for r in resp.data}
print(f"Empleados en BD: {len(todos)}")

# ── Obtener departamento del responsable directo ──────────────────────────────
def get_dept_responsable(emp_id: str, visitados: set = None) -> str:
    if visitados is None:
        visitados = set()
    if emp_id in visitados:
        return ""
    visitados.add(emp_id)
    emp = todos.get(emp_id)
    if not emp:
        return ""
    resp_id = emp.get("responsable_id")
    if not resp_id:
        return emp.get("departamento") or ""
    resp = todos.get(resp_id)
    if not resp:
        return emp.get("departamento") or ""
    dept_resp = resp.get("departamento") or ""
    if dept_resp:
        return dept_resp
    return get_dept_responsable(resp_id, visitados)

# ── Calcular cambios necesarios ───────────────────────────────────────────────
actualizaciones = []

for emp_id, emp in todos.items():
    resp_id = emp.get("responsable_id")
    if not resp_id:
        continue  # cabeza de jerarquia, no tocar

    resp_obj = todos.get(resp_id)
    if not resp_obj:
        continue

    dept_responsable = resp_obj.get("departamento") or ""
    if not dept_responsable:
        dept_responsable = get_dept_responsable(resp_id)

    dept_actual = emp.get("departamento") or ""

    if dept_responsable and dept_responsable != dept_actual:
        actualizaciones.append({
            "id":         emp_id,
            "nombre":     emp.get("apellidos_y_nombre", ""),
            "dept_nuevo": dept_responsable,
            "dept_actual": dept_actual,
        })

print(f"Empleados con departamento a actualizar: {len(actualizaciones)}")

# ── Aplicar o mostrar ─────────────────────────────────────────────────────────
if DRY_RUN:
    print("\nEjemplos de cambios (primeros 25):")
    print(f"  {'Nombre':<42} {'Dept actual':<32} -> Dept nuevo")
    print(f"  {'-'*110}")
    for a in actualizaciones[:25]:
        print(f"  {a['nombre']:<42} {a['dept_actual']:<32} -> {a['dept_nuevo']}")
else:
    actualizados = 0
    errores = 0
    for a in actualizaciones:
        try:
            sb.table("empleados").update({"departamento": a["dept_nuevo"]}).eq("id", a["id"]).execute()
            actualizados += 1
        except Exception as e:
            print(f"  ERROR {a['nombre']}: {e}")
            errores += 1

    print(f"  Actualizados: {actualizados}")
    print(f"  Errores:      {errores}")

# ── Resumen por departamento ──────────────────────────────────────────────────
from collections import Counter
if not DRY_RUN:
    resp3 = sb.table("empleados").select("departamento").execute()
    conteo = Counter(r.get("departamento") or "Sin departamento" for r in resp3.data)
    print(f"\nEmpleados por departamento tras la actualizacion:")
    for dept, cnt in sorted(conteo.items(), key=lambda x: -x[1]):
        print(f"  {dept:<45} {cnt} empleados")

print(f"\n{'='*60}")
if DRY_RUN:
    print("  DRY-RUN completado. Quita --dry-run para aplicar.")
else:
    print("  Departamentos propagados correctamente en Supabase.")
print(f"{'='*60}\n")
