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
    r = client.table("empleados").select("*").eq("email", email).execute()
    return r.data


class EmpleadoRepository:
    def get_todos_activos(self) -> list[Empleado]:
        rows = _fetch_empleados_activos()
        return [Empleado.from_dict(r) for r in rows]

    def get_activos(self, usuario: Empleado) -> list[Empleado]:
        """Empleados visibles para el usuario según su rol y departamento."""
        todos = self.get_todos_activos()
        if usuario.vista == "administrador":
            return todos
        # Responsable/coordinador: ve solo su departamento
        dept = usuario.departamento
        if dept:
            return [e for e in todos if e.departamento == dept]
        # Fallback: recursivo por responsable_id
        return _descendientes(usuario.id, todos)

    def get_by_email(self, email: str) -> Optional[Empleado]:
        rows = _fetch_empleado_by_email(email)
        if rows:
            return Empleado.from_dict(rows[0])
        return None

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

    def crear_empleado(self, apellidos_y_nombre: str, responsable_id: str,
                       jornada_semanal: float = 38.5, departamento: str = "") -> Empleado:
        client = get_client()
        data = {
            "apellidos_y_nombre": apellidos_y_nombre,
            "email": "",
            "activo": True,
            "es_responsable": False,
            "es_admin": False,
            "jornada_semanal": jornada_semanal,
            "responsable_id": responsable_id,
            "rol": "empleado",
            "departamento": departamento,
        }
        r = client.table("empleados").insert(data).execute()
        st.cache_data.clear()
        return Empleado.from_dict(r.data[0])

    def update_rol_completo(self, empleado_id: str, activo: bool, rol: str,
                             email: str, departamento: str) -> None:
        es_resp  = rol in ("responsable", "coordinador")
        es_admin = rol in ("administrador", "superadministrador")
        client = get_client()
        client.table("empleados").update({
            "activo": activo,
            "rol": rol,
            "es_responsable": es_resp,
            "es_admin": es_admin,
            "email": email,
            "departamento": departamento,
        }).eq("id", empleado_id).execute()
        st.cache_data.clear()
        logger.info("Rol actualizado %s → %s dept=%s", empleado_id, rol, departamento)

    # Compatibilidad con código anterior
    def update_rol_y_email(self, empleado_id: str, activo: bool, es_responsable: bool,
                            es_admin: bool, email: str) -> None:
        rol = "administrador" if es_admin else ("responsable" if es_responsable else "empleado")
        self.update_rol_completo(empleado_id, activo, rol, email, "")

    def update_jornada(self, empleado_id: str, jornada: float) -> None:
        client = get_client()
        client.table("empleados").update({"jornada_semanal": jornada}).eq("id", empleado_id).execute()
        st.cache_data.clear()

    def update_responsable(self, empleado_id: str, responsable_id) -> None:
        client = get_client()
        client.table("empleados").update({"responsable_id": responsable_id}).eq("id", empleado_id).execute()
        st.cache_data.clear()


def _descendientes(raiz_id: str, todos: list[Empleado]) -> list[Empleado]:
    hijos_de: dict[str, list[Empleado]] = {}
    for e in todos:
        if e.responsable_id:
            hijos_de.setdefault(e.responsable_id, []).append(e)
    resultado, cola, visitados = [], list(hijos_de.get(raiz_id, [])), {raiz_id}
    while cola:
        emp = cola.pop()
        if emp.id not in visitados:
            visitados.add(emp.id)
            resultado.append(emp)
            cola.extend(hijos_de.get(emp.id, []))
    return resultado
