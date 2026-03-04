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
    "coordinador":        "🔓 Vista su departamento",
    "responsable":        "🔓 Vista su departamento",
    "administrador":      "🌐 Vista toda la entidad",
    "superadministrador": "👑 SuperAdmin — gestión total",
}
_ROL_COLOR = {
    "empleado":           "#6c757d",
    "coordinador":        "#0d6efd",
    "responsable":        "#198754",
    "administrador":      "#6f42c1",
    "superadministrador": "#dc3545",
}
_NUEVO_DEPT = "＋ Nuevo departamento…"


def render_panel_control(usuario: Empleado) -> None:
    if usuario.email.strip().lower() != SUPERADMIN:
        st.error("Acceso denegado.")
        st.stop()

    st.title("⚙️ Panel de control")
    st.caption(
        "Solo accesible para **danielgilabert@prode.es**. "
        "Desde aquí puedes gestionar roles, departamentos, jerarquía y accesos al panel."
    )

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
    todos = _emp_repo.get_todos_con_inactivos()
    depts_existentes = sorted({e.departamento for e in todos if e.departamento})

    # ── Leyenda de roles ──────────────────────────────────────────
    with st.expander("ℹ️ Guía de roles", expanded=False):
        filas = [
            ("empleado",      "🔒", "Sin acceso a la app. Aparece en el resumen de su responsable."),
            ("coordinador",   "🔓", "Accede a la app. Ve solo su departamento. Sin configuración avanzada."),
            ("responsable",   "🔓", "Accede a la app. Ve su departamento completo. Puede configurar jornadas, festivos e incidencias."),
            ("administrador", "🌐", "Accede a la app. Ve toda la entidad. Puede generar informes globales."),
        ]
        for rol, ico, desc in filas:
            color = _ROL_COLOR[rol]
            st.markdown(
                f"<div style='margin:4px 0;padding:6px 12px;border-left:4px solid {color};"
                f"border-radius:0 6px 6px 0;background:#f8f9fa'>"
                f"<strong style='color:{color}'>{ico} {rol.capitalize()}</strong>"
                f"<span style='color:#555;margin-left:10px;font-size:0.9rem'>{desc}</span></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Contadores rápidos ────────────────────────────────────────
    from collections import Counter
    conteo = Counter(e.rol for e in todos)
    cols_c = st.columns(4)
    for i, rol in enumerate(_ROLES_UI):
        color = _ROL_COLOR[rol]
        cols_c[i].markdown(
            f"<div style='text-align:center;padding:10px;background:{color}15;"
            f"border:1px solid {color}44;border-radius:8px'>"
            f"<div style='font-size:1.4rem;font-weight:700;color:{color}'>{conteo.get(rol,0)}</div>"
            f"<div style='font-size:0.75rem;color:#555'>{rol.capitalize()}</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Filtros ───────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    filtro_rol    = col_f1.selectbox("Filtrar por rol", ["Todos"] + _ROLES_UI, key="f_rol")
    filtro_dept   = col_f2.selectbox("Filtrar por departamento", ["Todos"] + depts_existentes, key="f_dept")
    filtro_buscar = col_f3.text_input("Buscar nombre o correo", placeholder="Escribe para filtrar…", key="f_nom")

    lista = sorted(todos, key=lambda e: e.apellidos_y_nombre)
    if filtro_buscar:
        q = filtro_buscar.lower()
        lista = [e for e in lista if q in e.apellidos_y_nombre.lower() or q in (e.email or "").lower()]
    if filtro_rol != "Todos":
        lista = [e for e in lista if e.rol == filtro_rol]
    if filtro_dept != "Todos":
        lista = [e for e in lista if e.departamento == filtro_dept]

    st.markdown(f"**{len(lista)} empleado(s) encontrados**")
    st.markdown("---")

    # ── Lista de empleados ────────────────────────────────────────
    for emp in lista:
        color      = _ROL_COLOR.get(emp.rol, "#6c757d")
        vista_txt  = _VISTA_LABEL.get(emp.rol, "🔒 Sin acceso")
        dept_badge = f" · 🏢 {emp.departamento}" if emp.departamento else " · ⚠️ Sin departamento"
        icono      = "✅" if emp.activo else "❌"

        with st.expander(
            f"{icono}  {emp.apellidos_y_nombre}  ·  {emp.rol}{dept_badge}",
            expanded=False,
        ):
            if (emp.email or "").strip().lower() == SUPERADMIN:
                st.caption("👑 SuperAdministrador — no editable desde aquí.")
                continue

            # ── Fila 1: email, activo, rol ──────────────────────
            c1, c2, c3 = st.columns([3, 1, 2])
            nuevo_email  = c1.text_input("Email", value=emp.email or "", key=f"em_{emp.id}")
            nuevo_activo = c2.checkbox("Activo", value=emp.activo, key=f"ac_{emp.id}")
            nuevo_rol    = c3.selectbox(
                "Rol",
                options=_ROLES_UI,
                index=_ROLES_UI.index(emp.rol) if emp.rol in _ROLES_UI else 0,
                key=f"rol_{emp.id}",
                format_func=lambda r: f"{r.capitalize()} — {_VISTA_LABEL.get(r,'')}",
            )

            # ── Fila 2: departamento (solo si tiene acceso) ──────
            nuevo_dept = emp.departamento or ""
            if nuevo_rol != "empleado":
                opciones_dept = depts_existentes + [_NUEVO_DEPT]
                idx_dept = (
                    opciones_dept.index(emp.departamento)
                    if emp.departamento in opciones_dept
                    else len(opciones_dept) - 1
                )
                dept_sel = st.selectbox(
                    "🏢 Departamento",
                    options=opciones_dept,
                    index=idx_dept,
                    key=f"dsel_{emp.id}",
                    help="Selecciona el departamento. Todos los empleados del mismo departamento deben tener exactamente el mismo nombre.",
                )
                if dept_sel == _NUEVO_DEPT:
                    nuevo_dept = st.text_input(
                        "Nombre del nuevo departamento",
                        value="",
                        key=f"dnew_{emp.id}",
                        placeholder="Escribe el nombre exacto del nuevo departamento…",
                    )
                else:
                    nuevo_dept = dept_sel

                # Propagar a subordinados
                propagar = st.checkbox(
                    f"Propagar departamento '{nuevo_dept}' a todos sus subordinados",
                    value=False,
                    key=f"prop_{emp.id}",
                    help="Actualiza el departamento de todos los empleados que reportan a esta persona.",
                )

                st.caption(
                    f"Vista asignada: **{_VISTA_LABEL.get(nuevo_rol, '')}**  ·  "
                    f"Departamento visible en el semáforo: **{nuevo_dept or '(ninguno)'}**"
                )
            else:
                nuevo_dept = ""
                propagar   = False
                st.caption("Sin acceso a la app. No aparece en el semáforo.")

            # ── Guardar ──────────────────────────────────────────
            if st.button("💾 Guardar cambios", key=f"save_{emp.id}", use_container_width=True, type="primary"):
                if not nuevo_dept and nuevo_rol != "empleado":
                    st.warning("⚠️ Asigna un departamento antes de guardar.")
                else:
                    _emp_repo.update_rol_completo(
                        emp.id, nuevo_activo, nuevo_rol,
                        nuevo_email.strip(), nuevo_dept.strip()
                    )
                    if propagar and nuevo_dept:
                        _propagar_departamento(emp.id, nuevo_dept.strip(), todos)
                    st.success("✅ Guardado correctamente.")
                    st.rerun()


def _propagar_departamento(resp_id: str, dept: str, todos: list) -> None:
    """Actualiza el departamento de todos los subordinados directos e indirectos."""
    subordinados = [e for e in todos if e.responsable_id == resp_id]
    for sub in subordinados:
        _emp_repo.update_rol_completo(sub.id, sub.activo, sub.rol, sub.email or "", dept)
        _propagar_departamento(sub.id, dept, todos)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — JERARQUÍA
# ═══════════════════════════════════════════════════════════════════
def _tab_jerarquia() -> None:
    st.subheader("Árbol de jerarquía")
    st.caption(
        "Visualiza quién reporta a quién y reasigna responsables. "
        "La jerarquía es multinivel: un responsable puede tener coordinadores que a su vez tienen empleados."
    )

    todos   = _emp_repo.get_todos_con_inactivos()
    mapa    = {e.id: e for e in todos}
    jefes   = [e for e in todos if e.rol in ("responsable", "coordinador", "administrador", "superadministrador")]
    opc_ids = [""] + [e.id for e in sorted(jefes, key=lambda e: e.apellidos_y_nombre)]
    opc_nom = ["— Sin asignar —"] + [
        f"{e.apellidos_y_nombre} ({e.rol})" for e in sorted(jefes, key=lambda e: e.apellidos_y_nombre)
    ]

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
        color     = _ROL_COLOR.get(resp.rol, _AZUL)
        dept_badge = (
            f"&nbsp;<span style='background:{color};color:white;font-size:0.7rem;"
            f"padding:2px 8px;border-radius:10px'>{dept}</span>"
        ) if dept else ""
        indent_px = nivel * 28
        bg        = "#f0f4f8" if nivel == 0 else "#f7f9fc"

        st.markdown(
            f"<div style='margin-left:{indent_px}px;background:{bg};"
            f"border-left:4px solid {color};border-radius:0 8px 8px 0;"
            f"padding:9px 16px;margin-top:8px;margin-bottom:2px'>"
            f"<strong style='color:{color}'>{resp.apellidos_y_nombre}</strong>{dept_badge}"
            f"<span style='color:#6c757d;font-size:0.78rem;margin-left:10px'>"
            f"{resp.rol} &middot; {n_total} persona{'s' if n_total!=1 else ''}</span></div>",
            unsafe_allow_html=True,
        )

        for emp in sorted(equipo_de.get(resp.id, []), key=lambda e: e.apellidos_y_nombre):
            col_sp, col_nom, col_sel, col_btn = st.columns([0.2 + nivel * 0.3, 3.8, 4, 0.7])
            col_sp.markdown("")
            dept_emp = (
                f"<br><span style='font-size:0.7rem;color:#888'>🏢 {emp.departamento}</span>"
                if emp.departamento else ""
            )
            col_nom.markdown(
                f"<div style='padding-top:6px'><b>{emp.apellidos_y_nombre}</b>{dept_emp}</div>",
                unsafe_allow_html=True,
            )
            idx = opc_ids.index(emp.responsable_id) if emp.responsable_id in opc_ids else 0
            ni  = col_sel.selectbox(
                "jefe", range(len(opc_ids)),
                format_func=lambda i: opc_nom[i],
                index=idx, key=f"jer_{emp.id}", label_visibility="collapsed",
            )
            with col_btn:
                if st.button("💾", key=f"sjer_{emp.id}", help="Guardar responsable"):
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
            f"<strong>⚠️ Sin responsable asignado — {len(sin_asignar)} persona(s)</strong>"
            f"<span style='font-size:0.8rem;color:#666;margin-left:8px'>"
            f"Asígnales un responsable para que aparezcan en el departamento correcto.</span></div>",
            unsafe_allow_html=True,
        )
        for emp in sorted(sin_asignar, key=lambda e: e.apellidos_y_nombre):
            col_nom, col_sel, col_btn = st.columns([3.8, 4, 0.7])
            dept_txt = f" · 🏢 {emp.departamento}" if emp.departamento else ""
            col_nom.markdown(f"**{emp.apellidos_y_nombre}**{dept_txt}")
            ni = col_sel.selectbox(
                "jefe", range(len(opc_ids)),
                format_func=lambda i: opc_nom[i],
                index=0, key=f"jer_sa_{emp.id}", label_visibility="collapsed",
            )
            with col_btn:
                if st.button("💾", key=f"sjer_sa_{emp.id}"):
                    _emp_repo.update_responsable(emp.id, opc_ids[ni] or None)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — ACCESOS AL PANEL
# ═══════════════════════════════════════════════════════════════════
def _tab_accesos() -> None:
    st.subheader("Acceso al panel por responsable")
    st.caption(
        "Solo estos correos pueden ver el panel de semáforo por departamento. "
        "Los responsables y coordinadores normales no ven este panel a menos que estén aquí."
    )

    todos  = _emp_repo.get_todos_con_inactivos()
    emails = sorted(_acceso_repo.get_todos())

    if emails:
        for email in emails:
            emp_match = next((e for e in todos if (e.email or "").lower() == email.lower()), None)
            label = f"{emp_match.apellidos_y_nombre} · {emp_match.departamento}" if emp_match else email
            col_e, col_del = st.columns([6, 1])
            col_e.markdown(
                f"<div style='padding:5px 0'>"
                f"📧 <code>{email}</code>"
                f"<span style='color:#888;font-size:0.82rem;margin-left:10px'>{label if emp_match else ''}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if col_del.button("🗑", key=f"del_{email}", help="Revocar acceso"):
                _acceso_repo.remove_email(email)
                st.rerun()
    else:
        st.info("No hay correos autorizados aún.")

    st.divider()

    # Añadir desde lista de empleados con acceso
    col_a, col_b = st.columns([5, 2])
    con_acceso = sorted(
        [e for e in todos if e.rol in ("responsable", "coordinador", "administrador") and e.email],
        key=lambda e: e.apellidos_y_nombre,
    )
    opciones = ["— Selecciona empleado —"] + [
        f"{e.apellidos_y_nombre} ({e.email})" for e in con_acceso
        if (e.email or "").lower() not in [x.lower() for x in emails]
    ]
    sel = col_a.selectbox("Añadir desde empleados con acceso", opciones, key="add_emp_sel")
    if col_b.button("➕ Añadir", type="primary", use_container_width=True, key="add_emp_btn"):
        if sel != opciones[0]:
            email_nuevo = sel.split("(")[-1].rstrip(")")
            _acceso_repo.add_email(email_nuevo.strip())
            st.rerun()

    st.caption("O introduce un correo manualmente:")
    with st.form("add_email_manual", clear_on_submit=True):
        nuevo = st.text_input("Correo manual", placeholder="correo@prode.es")
        if st.form_submit_button("➕ Añadir correo manual", type="secondary"):
            if nuevo.strip():
                _acceso_repo.add_email(nuevo.strip())
                st.rerun()
