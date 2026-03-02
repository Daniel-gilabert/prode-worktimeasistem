import os
import streamlit as st
from services.auth_service import AuthService

_auth = AuthService()

_FOOTER = """
<style>
    .prode-footer {
        position: fixed;
        bottom: 0; left: 0; right: 0;
        background: #1a3d6e;
        color: #ccd9ed;
        text-align: center;
        font-size: 12px;
        padding: 7px 0;
        z-index: 9999;
        letter-spacing: 0.3px;
    }
    .prode-footer a { color: #7aaee0; text-decoration: none; }
</style>
<div class="prode-footer">
    Creado por <strong style="color:#fff;">Daniel Gilabert Cantero</strong>
    para <strong style="color:#fff;">Fundación PRODE</strong>
</div>
"""


def render_footer() -> None:
    st.markdown(_FOOTER, unsafe_allow_html=True)


def render_login() -> bool:
    if st.session_state.get("usuario") is not None:
        render_footer()
        return True

    _logo = "assets/logo-prode.png"
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        if os.path.exists(_logo):
            st.image(_logo, use_container_width=True)
        st.markdown(
            """
            <div style="
                padding:2rem 2rem 1.5rem;
                background:#ffffff;
                border-radius:12px;
                box-shadow:0 4px 24px rgba(26,61,110,.12);
                margin-top:0.5rem;
            ">
                <h2 style="color:#1a3d6e;text-align:center;margin-bottom:0.2rem;">
                    WorkTimeAsistem
                </h2>
                <p style="color:#2e6da4;text-align:center;font-size:0.9rem;margin-bottom:1.4rem;">
                    Fundación PRODE — Control Horario
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("form_login", clear_on_submit=False):
            email = st.text_input("Correo electrónico", placeholder="usuario@prode.es")
            submitted = st.form_submit_button("Acceder", use_container_width=True)

    render_footer()

    if submitted:
        if not email.strip():
            st.error("Introduce un correo electrónico.")
            return False
        usuario = _auth.login(email.strip().lower())
        if usuario:
            st.session_state["usuario"] = usuario
            st.rerun()
        else:
            st.error("Correo no autorizado o sin permisos de acceso.")

    return False
