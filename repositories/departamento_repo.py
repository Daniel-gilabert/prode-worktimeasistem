import logging
import streamlit as st
from repositories.base import get_client

logger = logging.getLogger(__name__)


@st.cache_data(ttl=120)
def _fetch_departamentos() -> dict[str, str]:
    client = get_client()
    r = client.table("departamentos").select("responsable_id,nombre").execute()
    return {row["responsable_id"]: row["nombre"] for row in r.data}


class DepartamentoRepository:

    def get_todos(self) -> dict[str, str]:
        return _fetch_departamentos()

    def get_nombre(self, responsable_id: str) -> str:
        return self.get_todos().get(responsable_id, "")

    def upsert(self, responsable_id: str, nombre: str) -> None:
        client = get_client()
        client.table("departamentos").upsert(
            {"responsable_id": responsable_id, "nombre": nombre.strip()},
            on_conflict="responsable_id",
        ).execute()
        st.cache_data.clear()
        logger.info("Departamento actualizado: %s → %s", responsable_id, nombre)
