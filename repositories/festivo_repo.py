import logging
from datetime import date, timedelta
import streamlit as st
from models.festivo import FestivoLocal, FestivoEmpleado
from repositories.base import get_client

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_festivos_locales(anno: int, responsable_id: str) -> list[dict]:
    client = get_client()
    r = (
        client.table("festivos_locales")
        .select("*")
        .eq("año", anno)
        .eq("responsable_id", responsable_id)
        .execute()
    )
    return r.data


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_todos_festivos_locales(anno: int) -> list[dict]:
    client = get_client()
    r = (
        client.table("festivos_locales")
        .select("*")
        .eq("año", anno)
        .execute()
    )
    return r.data


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_festivos_empleado() -> list[dict]:
    client = get_client()
    r = client.table("festivos_empleado").select("*").execute()
    return r.data


class FestivoRepository:
    def get_locales(self, anno: int, responsable_id: str) -> list[FestivoLocal]:
        rows = _fetch_festivos_locales(anno, responsable_id)
        return [FestivoLocal.from_dict(r) for r in rows]

    def get_asignaciones(self) -> list[FestivoEmpleado]:
        rows = _fetch_festivos_empleado()
        return [FestivoEmpleado.from_dict(r) for r in rows]

    def get_festivos_por_empleado(
        self, anno: int, responsable_id: str
    ) -> dict[str, set[date]]:
        festivos = self.get_locales(anno, responsable_id)
        asignaciones = self.get_asignaciones()

        festivo_map = {f.id: f.fecha for f in festivos}
        resultado: dict[str, set[date]] = {}

        for asig in asignaciones:
            if asig.festivo_id in festivo_map:
                resultado.setdefault(asig.empleado_id, set()).add(
                    festivo_map[asig.festivo_id]
                )
        return resultado

    def get_todos_festivos_por_empleado(self, anno: int) -> dict[str, set[date]]:
        rows = _fetch_todos_festivos_locales(anno)
        festivos = [FestivoLocal.from_dict(r) for r in rows]
        asignaciones = self.get_asignaciones()
        festivo_map = {f.id: f.fecha for f in festivos}
        resultado: dict[str, set[date]] = {}
        for asig in asignaciones:
            if asig.festivo_id in festivo_map:
                resultado.setdefault(asig.empleado_id, set()).add(
                    festivo_map[asig.festivo_id]
                )
        return resultado

    def get_ids_asignados(self, festivo_id: str) -> set[str]:
        asignaciones = self.get_asignaciones()
        return {a.empleado_id for a in asignaciones if a.festivo_id == festivo_id}

    def create_festivo(self, fecha: date, anno: int, descripcion: str, responsable_id: str) -> None:
        client = get_client()
        client.table("festivos_locales").insert({
            "fecha": fecha.isoformat(),
            "año": anno,
            "descripcion": descripcion,
            "responsable_id": responsable_id,
        }).execute()
        st.cache_data.clear()
        logger.info("Festivo local creado: %s — %s", fecha.isoformat(), descripcion)

    def delete_festivo(self, festivo_id: str) -> None:
        client = get_client()
        client.table("festivos_locales").delete().eq("id", festivo_id).execute()
        st.cache_data.clear()
        logger.info("Festivo local eliminado: %s", festivo_id)

    def guardar_asignaciones(self, festivo_id: str, empleado_ids: list[str]) -> None:
        client = get_client()
        client.table("festivos_empleado").delete().eq("festivo_id", festivo_id).execute()
        for emp_id in empleado_ids:
            client.table("festivos_empleado").insert({
                "festivo_id": festivo_id,
                "empleado_id": emp_id,
            }).execute()
        st.cache_data.clear()
        logger.info(
            "Asignaciones festivo %s actualizadas: %d empleados", festivo_id, len(empleado_ids)
        )
