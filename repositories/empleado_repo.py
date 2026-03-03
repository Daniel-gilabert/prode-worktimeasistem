import logging
import streamlit as st
from typing import Optional
from models.empleado import Empleado
from repositories.base import get_client

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_empleados_activos() -> list[dict]:
    client = get_client()
    r = client.table("empleados").select("*").eq("activo", True).execute()
    return r.data


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_empleado_by_email(email: str) -> list[dict]:
    client = get_client()
    r = (
        client.table("empleados")
        .select("*")
        .eq("email", email)
        .eq("activo", True)
        .execute()
    )
    return r.data


def _descendientes(raiz_id: str, todos: list[Empleado]) -> list[Empleado]:
    """Devuelve todos los empleados que están por debajo de raiz_id en la jerarquía (recursivo)."""
    hijos_de: dict[str, list[Empleado]] = {}
    for e in todos:
        pid = e.responsable_id
        if pid:
            hijos_de.setdefault(pid, []).append(e)

    resultado: list[Empleado] = []
    cola = list(hijos_de.get(raiz_id, []))
    visitados = {raiz_id}
    while cola:
        emp = cola.pop()
        if emp.id in visitados:
            continue
        visitados.add(emp.id)
        resultado.append(emp)
        cola.extend(hijos_de.get(emp.id, []))
    return resultado


class EmpleadoRepository:
    def get_todos_activos(self) -> list[Empleado]:
        rows = _fetch_empleados_activos()
        return [Empleado.from_dict(r) for r in rows]

    def get_activos(self, usuario: Empleado) -> list[Empleado]:
        """Devuelve empleados visibles para el usuario — recursivo hacia abajo."""
        rows = _fetch_empleados_activos()
        todos = [Empleado.from_dict(r) for r in rows]
        if usuario.es_admin:
            return todos
        return _descendientes(usuario.id, todos)

    def get_by_email(self, email: str) -> Optional[Empleado]:
        rows = _fetch_empleado_by_email(email)
        if rows:
            return Empleado.from_dict(rows[0])
        return None

    def crear_empleado(self, apellidos_y_nombre: str, responsable_id: str, jornada_semanal: float = 38.5) -> Empleado:
        client = get_client()
        data = {
            "apellidos_y_nombre": apellidos_y_nombre,
            "email": "",
            "activo": True,
            "es_responsable": False,
            "es_admin": False,
            "jornada_semanal": jornada_semanal,
            "responsable_id": responsable_id,
        }
        r = client.table("empleados").insert(data).execute()
        st.cache_data.clear()
        logger.info("Empleado creado: %s (responsable %s)", apellidos_y_nombre, responsable_id)
        return Empleado.from_dict(r.data[0])

    def update_jornada(self, empleado_id: str, jornada: float) -> None:
        client = get_client()
        client.table("empleados").update({"jornada_semanal": jornada}).eq(
            "id", empleado_id
        ).execute()
        st.cache_data.clear()
        logger.info("Jornada actualizada para empleado %s → %.1f h", empleado_id, jornada)

    def update_rol_y_email(self, empleado_id: str, activo: bool, es_responsable: bool, es_admin: bool, email: str) -> None:
        client = get_client()
        client.table("empleados").update({
            "activo": activo,
            "es_responsable": es_responsable,
            "es_admin": es_admin,
            "email": email,
        }).eq("id", empleado_id).execute()
        st.cache_data.clear()
        logger.info("Rol actualizado para empleado %s — activo=%s resp=%s admin=%s", empleado_id, activo, es_responsable, es_admin)

    def update_responsable(self, empleado_id: str, responsable_id) -> None:
        client = get_client()
        client.table("empleados").update({"responsable_id": responsable_id}).eq(
            "id", empleado_id
        ).execute()
        st.cache_data.clear()
        logger.info("Responsable de %s actualizado → %s", empleado_id, responsable_id)

    def get_todos_con_inactivos(self) -> list[Empleado]:
        client = get_client()
        r = client.table("empleados").select("*").order("apellidos_y_nombre").execute()
        vistos: set = set()
        resultado = []
        for row in r.data:
            if row["id"] not in vistos:
                vistos.add(row["id"])
                resultado.append(Empleado.from_dict(row))
        return resultado
