"""Servicios — lógica de negocio."""
from core.db import get_supabase, ejecutar_con_reintento
from utils.normalizacion import n, normalizar_codigo


def get_todos(solo_activos: bool = True) -> list[dict]:
    sb  = get_supabase()
    q   = sb.table("servicios").select(
        "*, empleados!empleado_base_id(nombre, apellidos), "
        "vehiculos!vehiculo_base_id(matricula, marca, modelo)"
    )
    if solo_activos:
        q = q.eq("activo", True)
    res = ejecutar_con_reintento(lambda: q.order("codigo").execute())
    data = res.data
    for s in data:
        emp = s.pop("empleados", None) or {}
        veh = s.pop("vehiculos", None) or {}
        s["empleado_base_nombre"]    = f"{emp.get('apellidos','')} {emp.get('nombre','')}".strip()
        s["vehiculo_base_matricula"] = veh.get("matricula", "")
    return data


def crear(datos: dict) -> dict:
    sb  = get_supabase()
    datos["codigo"] = normalizar_codigo(datos.get("codigo"))
    res = sb.table("servicios").insert(datos).execute()
    return res.data[0]


def actualizar(servicio_id: int, datos: dict) -> dict:
    sb  = get_supabase()
    res = sb.table("servicios").update(datos).eq("id", servicio_id).execute()
    return res.data[0]


def desactivar(servicio_id: int):
    get_supabase().table("servicios").update({"activo": False}).eq("id", servicio_id).execute()
