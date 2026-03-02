import logging
from datetime import date, timedelta
import streamlit as st
from models.incidencia import Incidencia, TipoIncidencia
from repositories.base import get_client

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_incidencias() -> list[dict]:
    client = get_client()
    r = client.table("incidencias").select("*").execute()
    return r.data


class IncidenciaRepository:
    def get_all(self) -> list[Incidencia]:
        rows = _fetch_incidencias()
        return [Incidencia.from_dict(r) for r in rows]

    def get_dias_por_empleado(self) -> dict[str, set[date]]:
        incidencias = self.get_all()
        resultado: dict[str, set[date]] = {}
        for inc in incidencias:
            dias: set[date] = set()
            delta = (inc.fecha_fin - inc.fecha_inicio).days
            for i in range(delta + 1):
                dias.add(inc.fecha_inicio + timedelta(days=i))
            resultado.setdefault(inc.empleado_id, set()).update(dias)
        return resultado

    def create(
        self,
        empleado_id: str,
        tipo: TipoIncidencia,
        fecha_inicio: date,
        fecha_fin: date,
        descripcion: str,
        created_by: str,
    ) -> None:
        client = get_client()
        client.table("incidencias").insert({
            "empleado_id": empleado_id,
            "tipo": tipo.value,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "descripcion": descripcion,
            "created_by": created_by,
        }).execute()
        st.cache_data.clear()
        logger.info(
            "Incidencia creada: empleado=%s tipo=%s %s→%s",
            empleado_id, tipo.value, fecha_inicio, fecha_fin,
        )
