import streamlit as st
from core.auth import check_login

from datetime import date, timedelta
from core.queries import get_empleados, get_ausencias, crear_ausencia, hay_solapamiento_ausencia
from core.db import get_supabase

st.set_page_config(page_title="Ausencias", layout="wide")

check_login()
st.title("Ausencias de empleados")

TIPOS_AUSENCIA = [
    "Vacaciones",
    "Baja mÃ©dica",
    "Baja por accidente",
    "Permiso retribuido",
    "Permiso no retribuido",
    "Maternidad / Paternidad",
    "Asuntos propios",
    "Otro",
]

COLORES_TIPO = {
    "Vacaciones":               ("#DBEAFE", "#1E40AF", "ðŸŒ´"),
    "Baja mÃ©dica":              ("#FEE2E2", "#991B1B", "ðŸ¥"),
    "Baja por accidente":       ("#FEF3C7", "#92400E", "ðŸš‘"),
    "Permiso retribuido":       ("#DCFCE7", "#166534", "âœ…"),
    "Permiso no retribuido":    ("#F3F4F6", "#374151", "ðŸ“‹"),
    "Maternidad / Paternidad":  ("#FDF4FF", "#6B21A8", "ðŸ‘¶"),
    "Asuntos propios":          ("#F0FDF4", "#14532D", "ðŸ "),
    "Otro":                     ("#F9FAFB", "#4B5563", "ðŸ“Œ"),
}

hoy = date.today()

tab_dashboard, tab_nueva, tab_historial = st.tabs([
    "Panel de ausencias", "Registrar ausencia", "Historial completo"
])

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TAB 1: DASHBOARD
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_dashboard:
    fecha_consulta = st.date_input("Ver ausencias para la fecha:", value=hoy, key="fecha_dash")

    empleados = get_empleados()
    try:
        todas_ausencias = get_ausencias()
    except Exception:
        todas_ausencias = []
        st.warning("No se pudo cargar la tabla de ausencias. Ejecuta el SQL de esquema en Supabase.")
        st.stop()

    # Ausentes en la fecha seleccionada
    ausentes_hoy = []
    for a in todas_ausencias:
        fi = date.fromisoformat(str(a["fecha_inicio"])[:10]) if a.get("fecha_inicio") else None
        ff = date.fromisoformat(str(a["fecha_fin"])[:10])    if a.get("fecha_fin")    else None
        if fi and ff and fi <= fecha_consulta <= ff:
            ausentes_hoy.append(a)

    total_emp    = len(empleados)
    total_aus    = len(ausentes_hoy)
    total_activo = total_emp - total_aus

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Total empleados",   total_emp)
    c2.metric("Activos hoy",       total_activo,  delta=None)
    c3.metric("Ausentes hoy",      total_aus,     delta=f"-{total_aus}" if total_aus else None,
              delta_color="inverse")

    st.divider()

    if not ausentes_hoy:
        st.success(f"NingÃºn empleado ausente el {fecha_consulta.strftime('%d/%m/%Y')}.")
    else:
        st.markdown(f"### Empleados ausentes el {fecha_consulta.strftime('%d/%m/%Y')}")
        for a in ausentes_hoy:
            emp = a.get("empleados") or {}
            nombre_emp = f"{emp.get('nombre','')} {emp.get('apellidos','')}".strip() or f"Empleado #{a['empleado_id']}"
            tipo = a.get("tipo", "Otro")
            bg, fg, ico = COLORES_TIPO.get(tipo, ("#F9FAFB", "#4B5563", "ðŸ“Œ"))
            fi = str(a["fecha_inicio"])[:10]
            ff = str(a["fecha_fin"])[:10]
            dias = (date.fromisoformat(ff) - date.fromisoformat(fi)).days + 1
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2.5, 2, 2, 1.5])
                c1.markdown(f"**ðŸ‘¤ {nombre_emp}**")
                c2.markdown(
                    f"<span style='background:{bg};color:{fg};padding:3px 10px;"
                    f"border-radius:99px;font-size:.8rem;font-weight:600'>{ico} {tipo}</span>",
                    unsafe_allow_html=True
                )
                c3.write(f"ðŸ“… {fi} â†’ {ff}")
                c4.write(f"**{dias} dÃ­a(s)**")
                if a.get("observaciones"):
                    st.caption(f"ðŸ“Œ {a['observaciones']}")

    # PrÃ³ximas ausencias (prÃ³ximos 30 dÃ­as)
    st.divider()
    st.markdown("### PrÃ³ximas ausencias (prÃ³ximos 30 dÃ­as)")
    limite = fecha_consulta + timedelta(days=30)
    proximas = []
    for a in todas_ausencias:
        fi = date.fromisoformat(str(a["fecha_inicio"])[:10]) if a.get("fecha_inicio") else None
        if fi and fecha_consulta < fi <= limite:
            proximas.append(a)
    proximas.sort(key=lambda x: x["fecha_inicio"])

    if not proximas:
        st.info("No hay ausencias programadas en los prÃ³ximos 30 dÃ­as.")
    else:
        for a in proximas:
            emp = a.get("empleados") or {}
            nombre_emp = f"{emp.get('nombre','')} {emp.get('apellidos','')}".strip()
            tipo = a.get("tipo", "Otro")
            bg, fg, ico = COLORES_TIPO.get(tipo, ("#F9FAFB", "#4B5563", "ðŸ“Œ"))
            fi = str(a["fecha_inicio"])[:10]
            ff = str(a["fecha_fin"])[:10]
            dias_para = (date.fromisoformat(fi) - fecha_consulta).days
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2.5, 2, 2, 1.5])
                c1.write(f"ðŸ‘¤ {nombre_emp}")
                c2.markdown(
                    f"<span style='background:{bg};color:{fg};padding:3px 10px;"
                    f"border-radius:99px;font-size:.8rem;font-weight:600'>{ico} {tipo}</span>",
                    unsafe_allow_html=True
                )
                c3.write(f"ðŸ“… {fi} â†’ {ff}")
                c4.caption(f"En {dias_para} dÃ­as")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TAB 2: REGISTRAR AUSENCIA
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_nueva:
    empleados = get_empleados()
    if not empleados:
        st.warning("No hay empleados registrados.")
    else:
        with st.form("form_nueva_ausencia"):
            opts_emp = {f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados}
            emp_sel  = st.selectbox("Empleado *", list(opts_emp.keys()))

            c1, c2 = st.columns(2)
            fi = c1.date_input("Fecha inicio *", value=hoy)
            ff = c2.date_input("Fecha fin *",    value=hoy)

            tipo = st.selectbox("Tipo de ausencia *", TIPOS_AUSENCIA)
            obs  = st.text_area("Observaciones (opcional)")

            if st.form_submit_button("Registrar ausencia", type="primary"):
                if ff < fi:
                    st.error("La fecha de fin no puede ser anterior a la de inicio.")
                else:
                    emp_id = opts_emp[emp_sel]
                    try:
                        if hay_solapamiento_ausencia(emp_id, fi, ff):
                            st.error("Ya existe una ausencia que se solapa con esas fechas para este empleado.")
                        else:
                            crear_ausencia(emp_id, fi, ff, tipo, obs or None)
                            st.success(f"Ausencia registrada: {emp_sel} â€” {tipo} del {fi} al {ff}.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TAB 3: HISTORIAL COMPLETO
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_historial:
    empleados = get_empleados()
    opts_filtro = {"Todos los empleados": None}
    opts_filtro.update({f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados})

    c1, c2 = st.columns(2)
    filtro_emp  = c1.selectbox("Filtrar por empleado", list(opts_filtro.keys()), key="hist_emp")
    filtro_tipo = c2.selectbox("Filtrar por tipo", ["Todos"] + TIPOS_AUSENCIA, key="hist_tipo")

    try:
        emp_id_filtro = opts_filtro[filtro_emp]
        ausencias = get_ausencias(emp_id_filtro)
    except Exception:
        ausencias = []

    if filtro_tipo != "Todos":
        ausencias = [a for a in ausencias if a.get("tipo") == filtro_tipo]

    st.write(f"**{len(ausencias)} registro(s)**")

    if not ausencias:
        st.info("No hay ausencias con los filtros seleccionados.")
    else:
        for a in ausencias:
            emp = a.get("empleados") or {}
            nombre_emp = f"{emp.get('nombre','')} {emp.get('apellidos','')}".strip() or f"Empleado #{a['empleado_id']}"
            tipo = a.get("tipo", "Otro")
            bg, fg, ico = COLORES_TIPO.get(tipo, ("#F9FAFB", "#4B5563", "ðŸ“Œ"))
            fi = str(a["fecha_inicio"])[:10]
            ff = str(a["fecha_fin"])[:10]
            dias = (date.fromisoformat(ff) - date.fromisoformat(fi)).days + 1

            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2.5, 2, 2, 1, 0.8])
                c1.write(f"ðŸ‘¤ **{nombre_emp}**")
                c2.markdown(
                    f"<span style='background:{bg};color:{fg};padding:3px 10px;"
                    f"border-radius:99px;font-size:.8rem;font-weight:600'>{ico} {tipo}</span>",
                    unsafe_allow_html=True
                )
                c3.write(f"ðŸ“… {fi} â†’ {ff}")
                c4.write(f"{dias} dÃ­a(s)")
                if c5.button("ðŸ—‘ï¸", key=f"del_aus_{a['id']}", help="Eliminar"):
                    try:
                        get_supabase().table("ausencias").delete().eq("id", a["id"]).execute()
                        st.success("Ausencia eliminada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                if a.get("observaciones"):
                    st.caption(f"ðŸ“Œ {a['observaciones']}")

