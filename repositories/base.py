import os
import logging
from supabase import create_client, Client
from config import load_runtime_env

load_runtime_env()

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_secret(key: str) -> str:
    """Lee de st.secrets (Streamlit Cloud) o de os.environ (local/.env)."""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return str(val).strip()
    except Exception:
        pass
    return os.environ.get(key, "").strip()


def get_client() -> Client:
    global _client
    if _client is None:
        load_runtime_env()
        url = _get_secret("SUPABASE_URL")
        key = _get_secret("SUPABASE_KEY")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL y SUPABASE_KEY deben estar definidos en .streamlit/secrets.toml "
                "o en el archivo .env / 1.env"
            )
        logger.debug("Conectando a Supabase: %s", url)
        _client = create_client(url, key)
        logger.debug("Cliente Supabase inicializado")
    return _client
