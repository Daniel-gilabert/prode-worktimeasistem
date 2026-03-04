import logging
import streamlit as st
from repositories.base import get_client

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_ignorados(responsable_id: str) -> set[str]:
    client = get_client()
    r = client.table("excel_ignorados").select("clave_sorted").eq("responsable_id", responsable_id).execute()
    return {row["clave_sorted"] for row in (r.data or [])}


class IgnoradosRepository:
    def get_por_responsable(self, responsable_id: str) -> set[str]:
        return _fetch_ignorados(responsable_id)

    def ignorar(self, responsable_id: str, clave_sorted: str) -> None:
        client = get_client()
        client.table("excel_ignorados").upsert({
            "responsable_id": responsable_id,
            "clave_sorted": clave_sorted,
        }).execute()
        st.cache_data.clear()
        logger.info("Ignorado permanente: responsable=%s clave=%s", responsable_id, clave_sorted)

    def restaurar(self, responsable_id: str, clave_sorted: str) -> None:
        client = get_client()
        client.table("excel_ignorados").delete().eq("responsable_id", responsable_id).eq("clave_sorted", clave_sorted).execute()
        st.cache_data.clear()
        logger.info("Restaurado ignorado: responsable=%s clave=%s", responsable_id, clave_sorted)
