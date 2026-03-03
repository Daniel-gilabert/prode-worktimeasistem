import streamlit as st
import pandas as pd
from models.empleado import Empleado
from repositories.empleado_repo import EmpleadoRepository
from repositories.panel_acceso_repo import PanelAccesoRepository
from repositories.departamento_repo import DepartamentoRepository

_emp_repo    = EmpleadoRepository()
_acceso_repo = PanelAccesoRepository()
_dept_repo   = DepartamentoRepository()

SUPERADMIN = "danielgilabert@prode.es"
_AZUL = "#1a3d6e"


def render_panel_control(usuario: Empleado) -> None:
    if usuario.email.strip().lower() != SUPERADMIN:
        st.error("Acceso denegado.")
        st.stop()

    st.title("⚙️ Panel de control")

    tabs = st.tabs(["👥 Roles y acceso", "🔗 Jerarquía", "🔑 Accesos al panel", "🏢 Departamentos"])

    with tabs[0]:
        _tab_roles()
    with tabs[1]:
        _tab_jerarquia()
    with tabs[2]:
        _tab_accesos()
    with tabs[3]:
        _tab_departamentos()


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — ROLES (tabla editable)
# ═══════════════════════════════════════════════════════════════════
def _tab_roles() -> None:
    st.subheader("Gestión de roles")
    todos = _emp_repo.get_todos_con_inactivos()

    df = pd.DataFrame([{
        "id":       e.id,
        "Nombre":   e.apellidos_y_nombre,
        "Email":    e.email or "",
        "Activo":   e.activo,
        "Responsable": e.es_responsable,
        "Admin":    e.es_admin,
    } for e in sorted(todos, key=lambda e: e.apellidos_y_nombre)])

    edited = st.data_editor(
        df.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Nombre":      st.column_config.TextColumn("Nombre", disabled=True),
            "Email":       st.column_config.TextColumn("Email"),
            "Activo":      st.column_config.CheckboxColumn("Activo"),
            "Responsable": st.column_config.CheckboxColumn("Responsable"),
            "Admin":       st.column_config.CheckboxColumn("Admin"),
        },
        key="tabla_roles",
    )

    if st.button("💾 Guardar todos los cambios", type="primary", use_container_width=True):
        ids = df["id"].tolist()
        cambios = 0
        for i, row in edited.iterrows():
            emp_id = ids[i]
            _emp_repo.update_rol_y_email(
                emp_id,
                bool(row["Activo"]),
                bool(row["Responsable"]),
                bool(row["Admin"]),
                str(row["Email"]).strip(),
            )
            cambios += 1
        st.success(f"✅ {cambios} empleados actualizados.")
        st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — JERARQUÍA (grupos visuales con reasignación inline)
# ═══════════════════════════════════════════════════════════════════
def _tab_jerarquia() -> None:
    st.subheader("Jerarquía de equipos")
    st.caption("Cada responsable ve a todo su equipo hacia abajo (multinivel). Cambia el responsable de cualquier persona aquí.")

    todos      = _emp_repo.get_todos_con_inactivos()
    dept_map   = _dept_repo.get_todos()
    mapa       = {e.id: e for e in todos}

    # Opciones para selectbox
    jefes      = [e for e in todos if e.es_responsable or e.es_admin]
    opc_ids    = [""] + [e.id for e in sorted(jefes, key=lambda e: e.apellidos_y_nombre)]
    opc_nombres= ["— Sin asignar —"] + [e.apellidos_y_nombre for e in sorted(jefes, key=lambda e: e.apellidos_y_nombre)]

    # Construir árbol: padre → hijos directos
    hijos_resp: dict[str, list[Empleado]] = {}   # responsable_id → sub-responsables
    equipo_de:  dict[str, list[Empleado]] = {}   # responsable_id → empleados normales
    ids_jefes = {e.id for e in jefes}

    for emp in todos:
        if not emp.activo:
            continue
        pid = emp.responsable_id
        if emp.id in ids_jefes:
            # Es sub-responsable
            if pid and pid in ids_jefes:
                hijos_resp.setdefault(pid, []).append(emp)
            # Si no tiene padre jefe → es raíz, se trata abajo
        else:
            # Es empleado normal
            if pid:
                equipo_de.setdefault(pid, []).append(emp)

    # Raíces: jefes cuyo responsable_id no apunta a otro jefe
    raices = sorted(
        [e for e in jefes if not (e.responsable_id and e.responsable_id in ids_jefes)],
        key=lambda e: e.apellidos_y_nombre,
    )

    sin_asignar = [
        e for e in todos
        if e.activo and e.id not in ids_jefes
        and (not e.responsable_id or e.responsable_id not in ids_jefes)
        and e.responsable_id not in {emp.id for emp in todos}
    ]
    # Más simple: sin responsable asignado en absoluto
    sin_asignar = [
        e for e in todos
        if e.activo and e.id not in ids_jefes and not e.responsable_id
    ]

    def _render_grupo(resp: Empleado, nivel: int) -> None:
        dept      = dept_map.get(resp.id, "")
        n_emps    = len(equipo_de.get(resp.id, []))
        n_subs    = len(hijos_resp.get(resp.id, []))
        n_total   = n_emps + n_subs
        rol_txt   = "👑 Admin" if resp.es_admin else "👤 Responsable"
        dept_badge = (
            f"&nbsp;<span style='background:{_AZUL};color:white;font-size:0.7rem;"
            f"padding:2px 7px;border-radius:10px'>{dept}</span>"
        ) if dept else ""
        indent_px  = nivel * 24
        borde_color = _AZUL if nivel == 0 else "#6c8ebf"
        bg_color    = "#f0f4f8" if nivel == 0 else "#f7f9fc"

        st.markdown(
            f"<div style='margin-left:{indent_px}px;background:{bg_color};"
            f"border-left:4px solid {borde_color};"
            f"border-radius:0 8px 8px 0;padding:9px 16px;margin-top:10px;margin-bottom:2px'>"
            f"<strong style='color:{_AZUL};font-size:{'1rem' if nivel==0 else '0.9rem'}'>"
            f"{resp.apellidos_y_nombre}</strong>{dept_badge}"
            f"<span style='color:#6c757d;font-size:0.78rem;margin-left:10px'>"
            f"{rol_txt} &middot; {n_total} persona{'s' if n_total!=1 else ''} a cargo</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Empleados directos de este responsable
        for emp in sorted(equipo_de.get(resp.id, []), key=lambda e: e.apellidos_y_nombre):
            sub_dept      = dept_map.get(emp.id, "")
            sub_dept_html = f"<br><span style='font-size:0.7rem;color:#888'>{sub_dept}</span>" if sub_dept else ""
            col_indent, col_nom, col_sel, col_btn = st.columns([0.2 + nivel * 0.3, 3.8, 4, 0.7])
            col_indent.markdown("")
            col_nom.markdown(
                f"<div style='padding-top:6px'><b>{emp.apellidos_y_nombre}</b>{sub_dept_html}</div>",
                unsafe_allow_html=True,
            )
            idx = opc_ids.index(emp.responsable_id) if emp.responsable_id in opc_ids else 0
            nuevo_idx = col_sel.selectbox(
                "jefe", options=range(len(opc_ids)),
                format_func=lambda i: opc_nombres[i],
                index=idx, key=f"jer_{emp.id}",
                label_visibility="collapsed",
            )
            with col_btn:
                st.markdown("<div style='padding-top:4px'></div>", unsafe_allow_html=True)
                if st.button("💾", key=f"sjer_{emp.id}"):
                    _emp_repo.update_responsable(emp.id, opc_ids[nuevo_idx] or None)
                    st.rerun()

        # Sub-responsables (recursivo)
        for sub in sorted(hijos_resp.get(resp.id, []), key=lambda e: e.apellidos_y_nombre):
            _render_grupo(sub, nivel + 1)

    # ── Renderizar árbol ──────────────────────────────────────────
    for raiz in raices:
        _render_grupo(raiz, 0)

    # ── Sin asignar ───────────────────────────────────────────────
    if sin_asignar:
        st.markdown(
            f"""<div style="background:#fff3cd;border-left:4px solid #ffc107;
            border-radius:0 8px 8px 0;padding:10px 16px;margin:16px 0 4px">
            <strong>⚠️ Sin responsable asignado</strong>
            <span style="color:#6c757d;font-size:0.85rem;margin-left:8px">{len(sin_asignar)} persona(s)</span>
            </div>""",
            unsafe_allow_html=True,
        )
        for emp in sorted(sin_asignar, key=lambda e: e.apellidos_y_nombre):
            col_nom, col_sel, col_btn = st.columns([3.8, 4, 0.7])
            col_nom.markdown(f"<div style='padding-top:6px'><b>{emp.apellidos_y_nombre}</b></div>", unsafe_allow_html=True)
            nuevo_idx = col_sel.selectbox(
                "jefe", options=range(len(opc_ids)),
                format_func=lambda i: opc_nombres[i],
                index=0, key=f"jer_sa_{emp.id}",
                label_visibility="collapsed",
            )
            with col_btn:
                st.markdown("<div style='padding-top:4px'></div>", unsafe_allow_html=True)
                if st.button("💾", key=f"sjer_sa_{emp.id}"):
                    _emp_repo.update_responsable(emp.id, opc_ids[nuevo_idx] or None)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — ACCESOS AL PANEL
# ═══════════════════════════════════════════════════════════════════
def _tab_accesos() -> None:
    st.subheader("Acceso al panel por responsable")
    st.caption("Solo estos correos pueden ver el panel de semáforo por responsable.")

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


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — DEPARTAMENTOS
# ═══════════════════════════════════════════════════════════════════
def _tab_departamentos() -> None:
    st.subheader("Nombres de departamento")
    st.caption("Este nombre aparece encima del semáforo y en todas las gráficas en lugar del apellido del responsable.")

    todos        = _emp_repo.get_todos_con_inactivos()
    responsables = sorted([e for e in todos if (e.es_responsable or e.es_admin) and e.activo],
                          key=lambda e: e.apellidos_y_nombre)
    dept_map     = _dept_repo.get_todos()

    for resp in responsables:
        col_nom, col_dept, col_btn = st.columns([3, 5, 1])
        col_nom.markdown(f"<div style='padding-top:8px'>{resp.apellidos_y_nombre}</div>", unsafe_allow_html=True)
        nuevo = col_dept.text_input(
            "dept", value=dept_map.get(resp.id, ""),
            key=f"dept_{resp.id}", label_visibility="collapsed",
            placeholder="Ej: Casa de Acogida de Córdoba",
        )
        with col_btn:
            if st.button("💾", key=f"sdept_{resp.id}"):
                _dept_repo.upsert(resp.id, nuevo)
                st.success("✓")
                st.rerun()
