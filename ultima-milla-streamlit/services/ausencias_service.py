"""Ausencias — lógica de negocio."""
from datetime import date
from core.db import get_supabase, ejecutar_con_reintento
from utils.validaciones import hay_solapamiento


def get_todas(empleado_id: int | None = None) -> list[dict]:
    sb = get_supabase()
    q  = sb.table("ausencias").select("*, empleados(nombre, apellidos)")
    if empleado_id:
        q = q.eq("empleado_id", empleado_id)
    res = ejecutar_con_reintento(lambda: q.order("fecha_inicio", desc=True).execute())
    return res.data


def crear(empleado_id: int, fi: date, ff: date,
          tipo: str, observaciones: str | None = None):
    todas = get_todas(empleado_id)
    if hay_solapamiento(todas, empleado_id, fi, ff):
        raise ValueError("Ya existe una ausencia que se solapa con esas fechas.")
    get_supabase().table("ausencias").insert({
        "empleado_id":  empleado_id,
        "fecha_inicio": str(fi),
        "fecha_fin":    str(ff),
        "tipo":         tipo,
        "observaciones": observaciones,
    }).execute()


def eliminar(ausencia_id: int):
    get_supabase().table("ausencias").delete().eq("id", ausencia_id).execute()
