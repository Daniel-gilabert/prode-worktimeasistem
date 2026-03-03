import streamlit as st
from models.empleado import Empleado
from repositories.empleado_repo import EmpleadoRepository
from repositories.panel_acceso_repo import PanelAccesoRepository
from repositories.departamento_repo import DepartamentoRepository

_emp_repo    = EmpleadoRepository()
_acceso_repo = PanelAccesoRepository()
_dept_repo   = DepartamentoRepository()

SUPERADMIN = "danielgilabert@prode.es"


def render_panel_control(usuario: Empleado) -> None:
    if usuario.email.strip().lower() != SUPERADMIN:
        st.error("Acceso denegado.")
        st.stop()

    st.title("Panel de control · Administración suprema")
    st.caption("Solo accesible para danielgilabert@prode.es")

    tabs = st.tabs([
        "👥 Empleados y roles",
        "🔗 Jerarquía (quién es de quién)",
        "🔑 Accesos al panel",
        "🏢 Departamentos",
    ])

    with tabs[0]:
        _tab_roles()
    with tabs[1]:
        _tab_jerarquia()
    with tabs[2]:
        _tab_accesos()
    with tabs[3]:
        _tab_departamentos()


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — ROLES
# ═══════════════════════════════════════════════════════════════════
def _tab_roles() -> None:
    st.subheader("Empleados activos e inactivos — gestión de roles")
    st.caption("Aquí puedes activar/desactivar empleados y cambiar sus roles.")

    todos = _emp_repo.get_todos_con_inactivos()
    if not todos:
        st.info("No hay empleados en la base de datos.")
        return

    for emp in sorted(todos, key=lambda e: e.apellidos_y_nombre):
        with st.expander(
            f"{'✅' if emp.activo else '❌'}  {emp.apellidos_y_nombre}"
            f"  {'· Admin' if emp.es_admin else '· Responsable' if emp.es_responsable else '· Empleado'}",
            expanded=False,
        ):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                email_val = st.text_input(
                    "Email", value=emp.email or "",
                    key=f"email_{emp.id}", label_visibility="visible",
                )
            activo     = col2.checkbox("Activo",       value=emp.activo,        key=f"activo_{emp.id}")
            es_resp    = col3.checkbox("Responsable",  value=emp.es_responsable,key=f"resp_{emp.id}")
            es_admin_  = col4.checkbox("Admin",        value=emp.es_admin,      key=f"adm_{emp.id}")

            if st.button("Guardar cambios", key=f"save_rol_{emp.id}", use_container_width=True):
                _emp_repo.update_rol_y_email(emp.id, activo, es_resp, es_admin_, email_val.strip())
                st.success("Guardado.")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — JERARQUÍA
# ═══════════════════════════════════════════════════════════════════
def _tab_jerarquia() -> None:
    st.subheader("Asignación: empleado → responsable")
    st.caption("Define quién es responsable de cada empleado.")

    todos = _emp_repo.get_todos_con_inactivos()
    responsables = [e for e in todos if e.es_responsable or e.es_admin]
    opciones_resp = {e.id: e.apellidos_y_nombre for e in responsables}
    opciones_resp[""] = "— Sin asignar —"

    empleados_no_resp = [e for e in todos if not e.es_responsable and not e.es_admin and e.activo]

    if not empleados_no_resp:
        st.info("No hay empleados sin rol de responsable.")
        return

    st.markdown(f"**{len(empleados_no_resp)} empleados activos**")

    for emp in sorted(empleados_no_resp, key=lambda e: e.apellidos_y_nombre):
        col_nom, col_sel, col_btn = st.columns([4, 4, 1])
        col_nom.markdown(f"**{emp.apellidos_y_nombre}**")

        opciones_ids  = [""] + [e.id for e in responsables]
        opciones_text = [opciones_resp[rid] for rid in opciones_ids]
        idx_actual    = opciones_ids.index(emp.responsable_id or "")

        sel_idx = col_sel.selectbox(
            "Responsable", options=range(len(opciones_ids)),
            format_func=lambda i: opciones_text[i],
            index=idx_actual,
            key=f"jerarquia_{emp.id}",
            label_visibility="collapsed",
        )
        with col_btn:
            if st.button("💾", key=f"save_jer_{emp.id}", help="Guardar"):
                nuevo_resp_id = opciones_ids[sel_idx] or None
                _emp_repo.update_responsable(emp.id, nuevo_resp_id)
                st.success("OK")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — ACCESOS AL PANEL
# ═══════════════════════════════════════════════════════════════════
def _tab_accesos() -> None:
    st.subheader("Correos con acceso al panel por responsable")
    st.caption("Solo estos correos verán el panel de semáforo por responsable.")

    emails = _acceso_repo.get_todos()
    if emails:
        st.markdown(f"**{len(emails)} correo(s) autorizados:**")
        for email in sorted(emails):
            col_e, col_del = st.columns([6, 1])
            col_e.markdown(f"📧 `{email}`")
            with col_del:
                if st.button("🗑", key=f"del_acceso_{email}", help="Quitar acceso"):
                    _acceso_repo.remove_email(email)
                    st.success(f"{email} eliminado.")
                    st.rerun()
    else:
        st.info("No hay correos autorizados todavía.")

    st.markdown("---")
    with st.form("form_add_email", clear_on_submit=True):
        nuevo = st.text_input("Nuevo correo", placeholder="correo@prode.es")
        if st.form_submit_button("Añadir acceso", type="primary"):
            if nuevo.strip():
                _acceso_repo.add_email(nuevo.strip())
                st.success(f"Acceso concedido a {nuevo.strip()}")
                st.rerun()
            else:
                st.warning("Escribe un correo válido.")


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — DEPARTAMENTOS
# ═══════════════════════════════════════════════════════════════════
def _tab_departamentos() -> None:
    st.subheader("Nombres de departamento por responsable")
    st.caption(
        "El nombre que asignes aquí aparecerá en el semáforo encima de cada tarjeta, "
        "en los títulos de detalle y en todas las gráficas."
    )

    todos = _emp_repo.get_todos_con_inactivos()
    responsables = [e for e in todos if (e.es_responsable or e.es_admin) and e.activo]
    dept_map = _dept_repo.get_todos()

    if not responsables:
        st.info("No hay responsables activos.")
        return

    for resp in sorted(responsables, key=lambda e: e.apellidos_y_nombre):
        col_nom, col_dept, col_btn = st.columns([3, 5, 1])
        col_nom.markdown(f"**{resp.apellidos_y_nombre}**")
        valor_actual = dept_map.get(resp.id, "")
        nuevo_dept = col_dept.text_input(
            "Departamento",
            value=valor_actual,
            key=f"dept_{resp.id}",
            label_visibility="collapsed",
            placeholder="Ej: Casa de Acogida de Córdoba",
        )
        with col_btn:
            if st.button("💾", key=f"save_dept_{resp.id}", help="Guardar"):
                _dept_repo.upsert(resp.id, nuevo_dept)
                st.success("Guardado.")
                st.rerun()
