import streamlit as st
from services.auth_service import AuthService

_auth = AuthService()


def render_login() -> bool:
    if st.session_state.get("usuario") is not None:
        return True

    st.markdown(
        """
        <div style="
            max-width:420px;
            margin:6rem auto 0;
            padding:2.5rem 2rem;
            background:#ffffff;
            border-radius:12px;
            box-shadow:0 4px 24px rgba(26,61,110,.12);
        ">
            <h2 style="color:#1a3d6e;text-align:center;margin-bottom:0.2rem;">
                WorkTimeAsistem
            </h2>
            <p style="color:#2e6da4;text-align:center;font-size:0.9rem;margin-bottom:1.8rem;">
                Fundación PRODE — Control Horario
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("form_login", clear_on_submit=False):
        email = st.text_input("Correo electrónico", placeholder="usuario@prode.org")
        submitted = st.form_submit_button("Acceder", use_container_width=True)

    if submitted:
        if not email.strip():
            st.error("Introduce un correo electrónico.")
            return False
        usuario = _auth.login(email)
        if usuario:
            st.session_state["usuario"] = usuario
            st.rerun()
        else:
            st.error("Correo no autorizado o sin permisos de acceso.")

    return False
