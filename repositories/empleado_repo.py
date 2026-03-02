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


class EmpleadoRepository:
    def get_todos_activos(self) -> list[Empleado]:
        rows = _fetch_empleados_activos()
        return [Empleado.from_dict(r) for r in rows]

    def get_activos(self, usuario: Empleado) -> list[Empleado]:
        rows = _fetch_empleados_activos()
        empleados = [Empleado.from_dict(r) for r in rows]
        if not usuario.es_admin:
            empleados = [e for e in empleados if e.responsable_id == usuario.id]
        return empleados

    def get_by_email(self, email: str) -> Optional[Empleado]:
        rows = _fetch_empleado_by_email(email)
        if rows:
            return Empleado.from_dict(rows[0])
        return None

    def update_jornada(self, empleado_id: str, jornada: float) -> None:
        client = get_client()
        client.table("empleados").update({"jornada_semanal": jornada}).eq(
            "id", empleado_id
        ).execute()
        st.cache_data.clear()
        logger.info("Jornada actualizada para empleado %s → %.1f h", empleado_id, jornada)
