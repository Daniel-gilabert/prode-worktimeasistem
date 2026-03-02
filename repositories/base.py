import os
import logging
from supabase import create_client, Client
import pathlib

def _cargar_env() -> None:
    try:
        import streamlit as st
        secrets = st.secrets
        for clave in ("SUPABASE_URL", "SUPABASE_KEY", "LOG_LEVEL", "POWERBI_URL"):
            if clave in secrets and clave not in os.environ:
                os.environ[clave] = str(secrets[clave])
        if os.environ.get("SUPABASE_URL"):
            return
    except Exception:
        pass

    base = pathlib.Path(__file__).resolve().parent.parent
    for nombre in (".env", "1.env", "1.env.txt"):
        candidato = base / nombre
        if candidato.exists():
            with open(candidato, encoding="utf-8-sig") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#") or "=" not in linea:
                        continue
                    clave, _, valor = linea.partition("=")
                    clave = clave.strip()
                    valor = valor.strip().strip('"').strip("'")
                    if clave and clave not in os.environ:
                        os.environ[clave] = valor
            return

_cargar_env()

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _cargar_env()
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL y SUPABASE_KEY deben estar definidos en el archivo .env o 1.env"
            )
        logger.debug("Conectando a Supabase: %s", url)
        _client = create_client(url, key)
        logger.debug("Cliente Supabase inicializado")
    return _client
