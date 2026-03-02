"""
Capa de acceso a datos con Supabase.
Adaptada a la estructura real de la tabla vehiculos existente.
"""
from datetime import date
from .db import get_supabase, ejecutar_con_reintento
from .models import (
    Empleado, Vehiculo, Sustitucion, Ausencia, Incidencia, EstadoServicio
)
from .estado import calcular_estado


# ── Helpers ──────────────────────────────────────────────────────
def _to_date(val) -> date | None:
    if val is None or str(val) in ("NaN", "None", ""):
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return None

def _clean(val) -> str | None:
    if val is None or str(val) in ("NaN", "None", ""):
        return None
    return str(val)

def _row_empleado(r: dict) -> Empleado:
    return Empleado(
        id=r["id"], nombre=r["nombre"], apellidos=r["apellidos"],
        dni=r["dni"], telefono=_clean(r.get("telefono")), email=_clean(r.get("email"))
    )

def _row_vehiculo(r: dict) -> Vehiculo:
    return Vehiculo(
        id=r["id"],
        id_vehiculo=_clean(r.get("id_vehiculo")) or "",
        matricula=r.get("matricula") or "",
        marca=r.get("marca") or "",
        modelo=r.get("modelo") or "",
        tipo=r.get("tipo") or "",
        itv_vigente_hasta=_to_date(r.get("itv_vigente_hasta")),
        seguro_vigente_hasta=_to_date(r.get("seguro_vigente_hasta")),
        bastidor=_clean(r.get("bastidor")),
        aseguradora=_clean(r.get("aseguradora")),
        poliza=_clean(r.get("poliza")),
    )


# ── Vehículos ─────────────────────────────────────────────────────
def get_vehiculos() -> list[dict]:
    sb = get_supabase()
    res = ejecutar_con_reintento(
        lambda: sb.table("vehiculos").select("*").neq("matricula", "").order("matricula").execute()
    )
    return [v for v in res.data if v.get("matricula")]

def actualizar_vehiculo(vehiculo_id: int, itv_vigente_hasta=None, seguro_vigente_hasta=None,
                         bastidor=None, aseguradora=None, poliza=None) -> dict:
    sb = get_supabase()
    datos = {}
    if itv_vigente_hasta   is not None: datos["itv_vigente_hasta"]   = str(itv_vigente_hasta)
    if seguro_vigente_hasta is not None: datos["seguro_vigente_hasta"] = str(seguro_vigente_hasta)
    if bastidor            is not None: datos["bastidor"]            = bastidor
    if aseguradora         is not None: datos["aseguradora"]         = aseguradora
    if poliza              is not None: datos["poliza"]              = poliza
    res = sb.table("vehiculos").update(datos).eq("id", vehiculo_id).execute()
    return res.data[0]


# ── Empleados ─────────────────────────────────────────────────────
def get_empleados() -> list[dict]:
    sb = get_supabase()
    res = ejecutar_con_reintento(
        lambda: sb.table("empleados").select("*").eq("activo", True).order("apellidos").execute()
    )
    return res.data

def crear_empleado(nombre, apellidos, dni, telefono=None, email=None) -> dict:
    sb = get_supabase()
    res = sb.table("empleados").insert({
        "nombre": nombre, "apellidos": apellidos, "dni": dni,
        "telefono": telefono or None, "email": email or None
    }).execute()
    return res.data[0]


# ── Servicios ─────────────────────────────────────────────────────
def get_servicios() -> list[dict]:
    sb = get_supabase()
    res = ejecutar_con_reintento(
        lambda: sb.table("servicios").select(
            "*, empleados!empleado_base_id(nombre, apellidos), vehiculos!vehiculo_base_id(matricula, marca, modelo)"
        ).eq("activo", True).order("codigo").execute()
    )
    rows = []
    for r in res.data:
        emp = r.get("empleados") or {}
        veh = r.get("vehiculos") or {}
        r["empleado_base_nombre"]     = f"{emp.get('nombre','')} {emp.get('apellidos','')}".strip()
        r["vehiculo_base_matricula"]  = veh.get("matricula", "")
        r["vehiculo_base_info"]       = f"{veh.get('matricula','')} ({veh.get('marca','')} {veh.get('modelo','')})"
        rows.append(r)
    return rows

def crear_servicio(codigo, descripcion, zona, empleado_base_id, vehiculo_base_id) -> dict:
    sb = get_supabase()
    res = sb.table("servicios").insert({
        "codigo": codigo, "descripcion": descripcion, "zona": zona or None,
        "empleado_base_id": empleado_base_id, "vehiculo_base_id": vehiculo_base_id,
    }).execute()
    return res.data[0]


# ── Sustituciones ─────────────────────────────────────────────────
def get_sustitucion_activa(servicio_id: int, tipo: str, fecha: date) -> dict | None:
    sb = get_supabase()
    res = (sb.table("sustituciones").select("*")
           .eq("servicio_id", servicio_id).eq("tipo", tipo)
           .lte("fecha_inicio", str(fecha)).gte("fecha_fin", str(fecha))
           .order("fecha_inicio", desc=True).limit(1).execute())
    return res.data[0] if res.data else None

def hay_solapamiento_sustitucion(servicio_id: int, tipo: str,
                                  fecha_inicio: date, fecha_fin: date,
                                  exclude_id: int = None) -> bool:
    sb = get_supabase()
    q = (sb.table("sustituciones").select("id")
         .eq("servicio_id", servicio_id).eq("tipo", tipo)
         .lte("fecha_inicio", str(fecha_fin)).gte("fecha_fin", str(fecha_inicio)))
    if exclude_id:
        q = q.neq("id", exclude_id)
    return len(q.execute().data) > 0

def crear_sustitucion(servicio_id, tipo, fecha_inicio, fecha_fin,
                       motivo=None, empleado_id=None, vehiculo_id=None) -> dict:
    sb = get_supabase()
    res = sb.table("sustituciones").insert({
        "servicio_id": servicio_id, "tipo": tipo,
        "empleado_id": empleado_id, "vehiculo_id": vehiculo_id,
        "fecha_inicio": str(fecha_inicio), "fecha_fin": str(fecha_fin),
        "motivo": motivo or None,
    }).execute()
    return res.data[0]

def get_sustituciones(servicio_id: int = None) -> list[dict]:
    sb = get_supabase()
    q = sb.table("sustituciones").select("*").order("fecha_inicio", desc=True)
    if servicio_id:
        q = q.eq("servicio_id", servicio_id)
    return q.execute().data


# ── Ausencias ─────────────────────────────────────────────────────
def get_ausencias_en_fecha(empleado_id: int, fecha: date) -> list[dict]:
    sb = get_supabase()
    return (sb.table("ausencias").select("*")
            .eq("empleado_id", empleado_id)
            .lte("fecha_inicio", str(fecha)).gte("fecha_fin", str(fecha))
            .execute()).data

def hay_solapamiento_ausencia(empleado_id: int, fecha_inicio: date,
                               fecha_fin: date, exclude_id: int = None) -> bool:
    sb = get_supabase()
    q = (sb.table("ausencias").select("id").eq("empleado_id", empleado_id)
         .lte("fecha_inicio", str(fecha_fin)).gte("fecha_fin", str(fecha_inicio)))
    if exclude_id:
        q = q.neq("id", exclude_id)
    return len(q.execute().data) > 0

def crear_ausencia(empleado_id, fecha_inicio, fecha_fin, tipo, observaciones=None) -> dict:
    sb = get_supabase()
    res = sb.table("ausencias").insert({
        "empleado_id": empleado_id,
        "fecha_inicio": str(fecha_inicio), "fecha_fin": str(fecha_fin),
        "tipo": tipo, "observaciones": observaciones or None,
    }).execute()
    return res.data[0]

def get_ausencias(empleado_id: int = None) -> list[dict]:
    sb = get_supabase()
    q = (sb.table("ausencias")
         .select("*, empleados(nombre, apellidos)")
         .order("fecha_inicio", desc=True))
    if empleado_id:
        q = q.eq("empleado_id", empleado_id)
    return q.execute().data


# ── Incidencias ───────────────────────────────────────────────────
def get_incidencias_en_fecha(vehiculo_id: int, fecha: date) -> list[dict]:
    sb = get_supabase()
    res = (sb.table("incidencias").select("*")
           .eq("vehiculo_id", vehiculo_id)
           .lte("fecha_inicio", str(fecha))
           .or_(f"fecha_fin.is.null,fecha_fin.gte.{fecha}")
           .execute())
    return res.data

def crear_incidencia(vehiculo_id, gravedad, descripcion, fecha_inicio, fecha_fin=None) -> dict:
    sb = get_supabase()
    res = sb.table("incidencias").insert({
        "vehiculo_id": vehiculo_id, "gravedad": gravedad, "descripcion": descripcion,
        "fecha_inicio": str(fecha_inicio),
        "fecha_fin": str(fecha_fin) if fecha_fin else None,
    }).execute()
    return res.data[0]

def cerrar_incidencia(incidencia_id: int, fecha_fin: date) -> dict:
    sb = get_supabase()
    res = (sb.table("incidencias").update({"fecha_fin": str(fecha_fin)})
           .eq("id", incidencia_id).execute())
    return res.data[0]

def get_incidencias(vehiculo_id: int = None) -> list[dict]:
    sb = get_supabase()
    q = (sb.table("incidencias")
         .select("*, vehiculos(matricula, marca, modelo)")
         .order("fecha_inicio", desc=True))
    if vehiculo_id:
        q = q.eq("vehiculo_id", vehiculo_id)
    return q.execute().data


# ── Cálculo estado de un servicio ────────────────────────────────
def calcular_estado_servicio(servicio: dict, fecha: date) -> EstadoServicio:
    sb = get_supabase()

    sust_emp = get_sustitucion_activa(servicio["id"], "empleado", fecha)
    sust_veh = get_sustitucion_activa(servicio["id"], "vehiculo", fecha)

    emp_id = sust_emp["empleado_id"] if sust_emp else servicio["empleado_base_id"]
    veh_id = sust_veh["vehiculo_id"] if sust_veh else servicio["vehiculo_base_id"]

    emp_row = sb.table("empleados").select("*").eq("id", emp_id).single().execute().data
    veh_row = sb.table("vehiculos").select("*").eq("id", veh_id).single().execute().data

    empleado = _row_empleado(emp_row)
    vehiculo = _row_vehiculo(veh_row)

    ausencias = [
        Ausencia(id=a["id"], empleado_id=a["empleado_id"],
                 fecha_inicio=_to_date(a["fecha_inicio"]),
                 fecha_fin=_to_date(a["fecha_fin"]),
                 tipo=a["tipo"], observaciones=a.get("observaciones"))
        for a in get_ausencias_en_fecha(emp_id, fecha)
    ]

    incidencias = [
        Incidencia(id=i["id"], vehiculo_id=i["vehiculo_id"],
                   gravedad=i["gravedad"], descripcion=i["descripcion"],
                   fecha_inicio=_to_date(i["fecha_inicio"]),
                   fecha_fin=_to_date(i.get("fecha_fin")))
        for i in get_incidencias_en_fecha(veh_id, fecha)
    ]

    def _sust(d):
        if not d:
            return None
        return Sustitucion(
            id=d["id"], servicio_id=d["servicio_id"], tipo=d["tipo"],
            empleado_id=d.get("empleado_id"), vehiculo_id=d.get("vehiculo_id"),
            fecha_inicio=_to_date(d["fecha_inicio"]),
            fecha_fin=_to_date(d["fecha_fin"]),
            motivo=d.get("motivo")
        )

    return calcular_estado(
        servicio_id=servicio["id"], fecha=fecha,
        empleado=empleado, vehiculo=vehiculo,
        ausencias=ausencias, incidencias=incidencias,
        sustitucion_empleado=_sust(sust_emp),
        sustitucion_vehiculo=_sust(sust_veh),
    )


# ── Dashboard completo ────────────────────────────────────────────
def calcular_dashboard(fecha: date) -> list[EstadoServicio]:
    servicios = get_servicios()
    resultados = []
    for s in servicios:
        try:
            resultados.append(calcular_estado_servicio(s, fecha))
        except Exception as e:
            from .models import MotivoEstado, EstadoServicio
            resultados.append(EstadoServicio(
                servicio_id=s["id"], fecha=fecha, estado="NO_OPERATIVO",
                motivos=[MotivoEstado("ERROR", str(e))],
                empleado_nombre=s.get("empleado_base_nombre", ""),
                vehiculo_matricula=s.get("vehiculo_base_matricula", ""),
            ))
    return resultados
