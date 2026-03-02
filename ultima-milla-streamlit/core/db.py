from supabase import create_client, Client
import streamlit as st
import time


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def ejecutar_con_reintento(func, reintentos: int = 3, espera: float = 1.5):
    """Ejecuta una función que llama a Supabase con reintentos automáticos."""
    ultimo_error = None
    for intento in range(reintentos):
        try:
            return func()
        except Exception as e:
            ultimo_error = e
            nombre = type(e).__name__
            if any(x in nombre for x in ("ReadError", "ConnectError", "TimeoutError", "NetworkError")):
                if intento < reintentos - 1:
                    time.sleep(espera)
                    continue
            raise
    raise ultimo_error
