import streamlit as st
import hashlib


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_login() -> bool:
    """Muestra pantalla de login si no hay sesión activa. Devuelve True si autenticado."""
    if st.session_state.get("autenticado"):
        return True

    usuarios = st.secrets.get("usuarios", {})
    if not usuarios:
        st.error("No hay usuarios configurados en secrets.toml")
        st.stop()

    st.markdown("""
    <div style='max-width:400px;margin:80px auto 0;text-align:center'>
        <h1 style='font-size:2rem'>🚚 Control Operativo</h1>
        <p style='color:#666;margin-bottom:32px'>Última Milla — Fundación Prode</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_login"):
            usuario  = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                hash_introducido = _hash(password)
                if usuario in usuarios and usuarios[usuario] == hash_introducido:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"]     = usuario
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

    st.stop()
    return False


def logout():
    st.session_state.pop("autenticado", None)
    st.session_state.pop("usuario", None)
    st.rerun()
