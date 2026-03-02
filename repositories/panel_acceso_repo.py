import logging
import streamlit as st
from repositories.base import get_client

logger = logging.getLogger(__name__)


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_emails_autorizados() -> list[str]:
    client = get_client()
    r = client.table("panel_acceso").select("email").execute()
    return [row["email"].strip().lower() for row in r.data]


class PanelAccesoRepository:
    def tiene_acceso(self, email: str) -> bool:
        autorizados = _fetch_emails_autorizados()
        return email.strip().lower() in autorizados

    def get_todos(self) -> list[str]:
        return _fetch_emails_autorizados()

    def add_email(self, email: str) -> None:
        client = get_client()
        client.table("panel_acceso").insert({"email": email.strip().lower()}).execute()
        st.cache_data.clear()
        logger.info("Acceso panel concedido a: %s", email)

    def remove_email(self, email: str) -> None:
        client = get_client()
        client.table("panel_acceso").delete().eq("email", email.strip().lower()).execute()
        st.cache_data.clear()
        logger.info("Acceso panel revocado a: %s", email)
