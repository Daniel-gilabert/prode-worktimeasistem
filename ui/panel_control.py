import streamlit as st
from models.empleado import Empleado, ROLES_VALIDOS
from repositories.empleado_repo import EmpleadoRepository
from repositories.panel_acceso_repo import PanelAccesoRepository

_emp_repo    = EmpleadoRepository()
_acceso_repo = PanelAccesoRepository()

SUPERADMIN   = "danielgilabert@prode.es"
_AZUL        = "#1a3d6e"
_ROLES_UI    = ["empleado", "coordinador", "responsable", "administrador"]
_VISTA_LABEL = {
    "empleado":           "🔒 Sin acceso",
    "coordinador":        "🔓 Vista responsable",
    "responsable":        "🔓 Vista responsable",
    "administrador":      "🔓 Vista administrador",
    "superadministrador": "👑 SuperAdmin",
}


def render_panel_control(usuario: Empleado) -> None:
    if usuario.email.strip().lower() != SUPERADMIN:
        st.error("Acceso denegado.")
        st.stop()

    st.title("⚙️ Panel de control")

    tabs = st.tabs(["👥 Roles y acceso", "🔗 Jerarquía", "🔑 Accesos al panel"])

    with tabs[0]:
        _tab_roles()
    with tabs[1]:
        _tab_jerarquia()
    with tabs[2]:
        _tab_accesos()


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — ROLES Y ACCESO
# ═══════════════════════════════════════════════════════════════════
def _tab_roles() -> None:
    st.subheader("Empleados — roles, departamento y acceso")
    st.caption(
        "**Responsable / Coordinador** → acceso con vista de su departamento.  "
        "**Administrador** → ve toda la entidad.  "
        "**Empleado** → sin acceso a la app."
    )

    todos = _emp_repo.get_todos_con_inactivos()
    depts_existentes = sorted({e.departamento for e in todos if e.departamento})

    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    filtro_rol    = col_f1.selectbox("Rol", ["Todos"] + _ROLES_UI, key="f_rol")
    filtro_dept   = col_f2.selectbox("Departamento", ["Todos"] + depts_existentes, key="f_dept")
    filtro_buscar = col_f3.text_input("Buscar nombre", placeholder="Escribe para filtrar…", key="f_nom")

    lista = sorted(todos, key=lambda e: e.apellidos_y_nombre)
    if filtro_buscar:
        lista = [e for e in lista if filtro_buscar.lower() in e.apellidos_y_nombre.lower()]
    if filtro_rol != "Todos":
        lista = [e for e in lista if e.rol == filtro_rol]
    if filtro_dept != "Todos":
        lista = [e for e in lista if e.departamento == filtro_dept]

    st.markdown(f"**{len(lista)} empleado(s)**")
    st.markdown("---")

    for emp in lista:
        vista_txt  = _VISTA_LABEL.get(emp.rol, "🔒 Sin acceso")
        dept_badge = f"  ·  🏢 {emp.departamento}" if emp.departamento else ""
        icono      = "✅" if emp.activo else "❌"

        with st.expander(
            f"{icono}  {emp.apellidos_y_nombre}  ·  {emp.rol}{dept_badge}  ·  {vista_txt}",
            expanded=False,
        ):
            if emp.email.strip().lower() == SUPERADMIN:
                st.caption("👑 SuperAdministrador — no editable desde aquí.")
                continue

            c1, c2, c3 = st.columns([3, 2, 2])
            nuevo_email  = c1.text_input("Email", value=emp.email or "", key=f"em_{emp.id}")
            nuevo_activo = c2.checkbox("Activo", value=emp.activo, key=f"ac_{emp.id}")
            nuevo_rol    = c3.selectbox(
                "Rol", options=_ROLES_UI,
                index=_ROLES_UI.index(emp.rol) if emp.rol in _ROLES_UI else 0,
                key=f"rol_{emp.id}",
            )

            nuevo_dept = emp.departamento
            if nuevo_rol != "empleado":
                col_d1, col_d2 = st.columns([5, 2])
                nuevo_dept = col_d1.text_input(
                    "Departamento", value=emp.departamento,
                    key=f"dept_{emp.id}",
                    placeholder="Casa de Acogida de Córdoba…",
                    help="Escribe exactamente el mismo nombre para agrupar empleados en el mismo departamento.",
                )
                if depts_existentes:
                    dept_sel = col_d2.selectbox(
                        "Copiar", options=["—"] + depts_existentes,
                        key=f"deptsel_{emp.id}", label_visibility="collapsed",
                    )
                    if dept_sel != "—":
                        nuevo_dept = dept_sel
                st.caption(f"Vista asignada: **{_VISTA_LABEL.get(nuevo_rol, '')}**")
            else:
                nuevo_dept = ""
                st.caption("Sin acceso a la app.")

            if st.button("💾 Guardar", key=f"save_{emp.id}", use_container_width=True, type="primary"):
                _emp_repo.update_rol_completo(
                    emp.id, nuevo_activo, nuevo_rol,
                    nuevo_email.strip(), nuevo_dept.strip()
                )
                st.success("✅ Guardado.")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — JERARQUÍA
# ═══════════════════════════════════════════════════════════════════
def _tab_jerarquia() -> None:
    st.subheader("Árbol de jerarquía")
    st.caption("Visualiza quién reporta a quién y reasigna si necesitas cambiar la estructura.")

    todos    = _emp_repo.get_todos_con_inactivos()
    mapa     = {e.id: e for e in todos}
    jefes    = [e for e in todos if e.rol in ("responsable", "coordinador", "administrador", "superadministrador")]
    opc_ids  = [""] + [e.id for e in sorted(jefes, key=lambda e: e.apellidos_y_nombre)]
    opc_nom  = ["— Sin asignar —"] + [e.apellidos_y_nombre for e in sorted(jefes, key=lambda e: e.apellidos_y_nombre)]

    hijos_resp: dict[str, list] = {}
    equipo_de:  dict[str, list] = {}
    ids_jefes  = {e.id for e in jefes}

    for emp in [e for e in todos if e.activo]:
        pid = emp.responsable_id
        if emp.id in ids_jefes:
            if pid and pid in ids_jefes:
                hijos_resp.setdefault(pid, []).append(emp)
        else:
            if pid:
                equipo_de.setdefault(pid, []).append(emp)

    raices = sorted(
        [e for e in jefes if not e.responsable_id or e.responsable_id not in ids_jefes],
        key=lambda e: e.apellidos_y_nombre,
    )
    sin_asignar = [e for e in todos if e.activo and e.id not in ids_jefes and not e.responsable_id]

    def _render_grupo(resp: Empleado, nivel: int) -> None:
        dept      = resp.departamento
        n_emps    = len(equipo_de.get(resp.id, []))
        n_subs    = len(hijos_resp.get(resp.id, []))
        n_total   = n_emps + n_subs
        dept_badge = (f"&nbsp;<span style='background:{_AZUL};color:white;font-size:0.7rem;"
                      f"padding:2px 7px;border-radius:10px'>{dept}</span>") if dept else ""
        indent_px  = nivel * 24
        bg         = "#f0f4f8" if nivel == 0 else "#f7f9fc"

        st.markdown(
            f"<div style='margin-left:{indent_px}px;background:{bg};"
            f"border-left:4px solid {_AZUL};border-radius:0 8px 8px 0;"
            f"padding:9px 16px;margin-top:8px;margin-bottom:2px'>"
            f"<strong style='color:{_AZUL}'>{resp.apellidos_y_nombre}</strong>{dept_badge}"
            f"<span style='color:#6c757d;font-size:0.78rem;margin-left:10px'>"
            f"{resp.rol} &middot; {n_total} persona{'s' if n_total!=1 else ''}</span></div>",
            unsafe_allow_html=True,
        )
        for emp in sorted(equipo_de.get(resp.id, []), key=lambda e: e.apellidos_y_nombre):
            col_sp, col_nom, col_sel, col_btn = st.columns([0.2 + nivel*0.3, 3.8, 4, 0.7])
            col_sp.markdown("")
            dept_emp = f"<br><span style='font-size:0.7rem;color:#888'>{emp.departamento}</span>" if emp.departamento else ""
            col_nom.markdown(f"<div style='padding-top:6px'><b>{emp.apellidos_y_nombre}</b>{dept_emp}</div>", unsafe_allow_html=True)
            idx = opc_ids.index(emp.responsable_id) if emp.responsable_id in opc_ids else 0
            ni  = col_sel.selectbox("jefe", range(len(opc_ids)), format_func=lambda i: opc_nom[i],
                                    index=idx, key=f"jer_{emp.id}", label_visibility="collapsed")
            with col_btn:
                if st.button("💾", key=f"sjer_{emp.id}"):
                    _emp_repo.update_responsable(emp.id, opc_ids[ni] or None)
                    st.rerun()
        for sub in sorted(hijos_resp.get(resp.id, []), key=lambda e: e.apellidos_y_nombre):
            _render_grupo(sub, nivel + 1)

    for raiz in raices:
        _render_grupo(raiz, 0)

    if sin_asignar:
        st.markdown(
            f"<div style='background:#fff3cd;border-left:4px solid #ffc107;"
            f"border-radius:0 8px 8px 0;padding:10px 16px;margin:16px 0 4px'>"
            f"<strong>⚠️ Sin responsable asignado — {len(sin_asignar)} persona(s)</strong></div>",
            unsafe_allow_html=True,
        )
        for emp in sorted(sin_asignar, key=lambda e: e.apellidos_y_nombre):
            col_nom, col_sel, col_btn = st.columns([3.8, 4, 0.7])
            col_nom.markdown(f"**{emp.apellidos_y_nombre}**")
            ni = col_sel.selectbox("jefe", range(len(opc_ids)), format_func=lambda i: opc_nom[i],
                                   index=0, key=f"jer_sa_{emp.id}", label_visibility="collapsed")
            with col_btn:
                if st.button("💾", key=f"sjer_sa_{emp.id}"):
                    _emp_repo.update_responsable(emp.id, opc_ids[ni] or None)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — ACCESOS AL PANEL
# ═══════════════════════════════════════════════════════════════════
def _tab_accesos() -> None:
    st.subheader("Acceso al panel por responsable")
    st.caption("Solo estos correos pueden ver el panel de semáforo por departamento.")

    emails = sorted(_acceso_repo.get_todos())
    if emails:
        for email in emails:
            col_e, col_del = st.columns([6, 1])
            col_e.markdown(f"📧 `{email}`")
            if col_del.button("🗑", key=f"del_{email}"):
                _acceso_repo.remove_email(email)
                st.rerun()
    else:
        st.info("No hay correos autorizados.")

    st.divider()
    with st.form("add_email", clear_on_submit=True):
        nuevo = st.text_input("Añadir correo", placeholder="correo@prode.es")
        if st.form_submit_button("➕ Añadir", type="primary"):
            if nuevo.strip():
                _acceso_repo.add_email(nuevo.strip())
                st.rerun()
