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
# TAB 2 — JERARQUÍA (árbol multinivel)
# ═══════════════════════════════════════════════════════════════════
def _tab_jerarquia() -> None:
    st.subheader("Árbol de jerarquía — multinivel")
    st.caption(
        "Cada persona ve a todos los que están por debajo de ella en el árbol, "
        "pero nunca hacia arriba. Puedes reasignar cualquier empleado desde aquí."
    )

    todos     = _emp_repo.get_todos_con_inactivos()
    dept_map  = _dept_repo.get_todos()
    mapa      = {e.id: e for e in todos}

    # Opciones para el selector de reasignación (todos los que pueden ser jefes)
    posibles_jefes = [e for e in todos if e.es_responsable or e.es_admin]
    opc_ids   = [""] + [e.id for e in sorted(posibles_jefes, key=lambda e: e.apellidos_y_nombre)]
    opc_text  = ["— Sin asignar —"] + [e.apellidos_y_nombre for e in sorted(posibles_jefes, key=lambda e: e.apellidos_y_nombre)]

    # Construir adjacency list: parent_id → [hijos]
    hijos: dict[str, list] = {e.id: [] for e in todos}
    raices: list = []
    for emp in todos:
        pid = emp.responsable_id
        if pid and pid in hijos:
            hijos[pid].append(emp)
        else:
            raices.append(emp)

    # Ordenar raíces: primero admins/responsables, luego por nombre
    raices = sorted(raices, key=lambda e: (not (e.es_admin or e.es_responsable), e.apellidos_y_nombre))

    # ── Árbol visual (HTML) + reasignación inline ──────────────────
    def _html_nodo(emp, nivel: int) -> str:
        indent   = nivel * 28
        icono    = "👑" if emp.es_admin else ("👤" if emp.es_responsable else ("✅" if emp.activo else "❌"))
        dept     = dept_map.get(emp.id, "")
        subtexto = f"<span style='color:#888;font-size:0.75rem'> · {dept}</span>" if dept else ""
        color    = "#1a3d6e" if (emp.es_admin or emp.es_responsable) else ("#212529" if emp.activo else "#adb5bd")
        n_hijos  = len(hijos.get(emp.id, []))
        badge    = f"<span style='background:#e9ecef;color:#495057;font-size:0.7rem;border-radius:4px;padding:1px 6px;margin-left:6px'>{n_hijos} ↓</span>" if n_hijos else ""
        return (
            f"<div style='margin-left:{indent}px;padding:5px 0;border-left:2px solid #dee2e6;"
            f"padding-left:10px;margin-bottom:2px'>"
            f"<span style='font-weight:600;color:{color}'>{icono} {emp.apellidos_y_nombre}</span>"
            f"{subtexto}{badge}"
            f"</div>"
        )

    def _renderizar_rama(emp, nivel: int) -> None:
        st.markdown(_html_nodo(emp, nivel), unsafe_allow_html=True)
        for hijo in sorted(hijos.get(emp.id, []), key=lambda e: e.apellidos_y_nombre):
            _renderizar_rama(hijo, nivel + 1)

    # Árbol visual
    with st.expander("🌳 Ver árbol completo", expanded=True):
        for raiz in raices:
            _renderizar_rama(raiz, 0)

    st.divider()

    # ── Sección de reasignación ────────────────────────────────────
    st.markdown("#### Reasignar empleados")
    st.caption("Busca un empleado y cámbialo de responsable.")

    buscar = st.text_input("Filtrar por nombre", placeholder="Escribe para filtrar...", key="jer_buscar")
    lista_reasig = [
        e for e in sorted(todos, key=lambda e: e.apellidos_y_nombre)
        if buscar.lower() in e.apellidos_y_nombre.lower()
    ] if buscar else []

    if buscar and not lista_reasig:
        st.caption("Sin coincidencias.")

    for emp in lista_reasig:
        jefe_actual = mapa.get(emp.responsable_id or "") if emp.responsable_id else None
        jefe_nombre = jefe_actual.apellidos_y_nombre if jefe_actual else "Sin asignar"
        col_nom, col_sel, col_btn = st.columns([3.5, 4, 0.8])
        col_nom.markdown(
            f"**{emp.apellidos_y_nombre}**  \n"
            f"<span style='font-size:0.75rem;color:#6c757d'>Actual: {jefe_nombre}</span>",
            unsafe_allow_html=True,
        )
        idx_actual = opc_ids.index(emp.responsable_id or "") if (emp.responsable_id or "") in opc_ids else 0
        sel_idx = col_sel.selectbox(
            "Nuevo responsable", options=range(len(opc_ids)),
            format_func=lambda i: opc_text[i],
            index=idx_actual,
            key=f"jer_{emp.id}",
            label_visibility="collapsed",
        )
        with col_btn:
            if st.button("💾", key=f"sjer_{emp.id}", help="Guardar"):
                nuevo = opc_ids[sel_idx] or None
                _emp_repo.update_responsable(emp.id, nuevo)
                st.success("Guardado")
                st.rerun()

    # Sin asignar — siempre visible
    sin_asignar = [e for e in todos if not e.responsable_id and not e.es_admin]
    if sin_asignar:
        st.markdown("---")
        st.markdown(f"**⚠️ {len(sin_asignar)} empleado(s) sin responsable asignado:**")
        for emp in sorted(sin_asignar, key=lambda e: e.apellidos_y_nombre):
            col_nom, col_sel, col_btn = st.columns([3.5, 4, 0.8])
            col_nom.markdown(f"**{emp.apellidos_y_nombre}**")
            sel_idx = col_sel.selectbox(
                "Responsable", options=range(len(opc_ids)),
                format_func=lambda i: opc_text[i],
                index=0, key=f"jer_sa_{emp.id}",
                label_visibility="collapsed",
            )
            with col_btn:
                if st.button("💾", key=f"sjer_sa_{emp.id}", help="Asignar"):
                    nuevo = opc_ids[sel_idx] or None
                    _emp_repo.update_responsable(emp.id, nuevo)
                    st.success("Guardado")
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
