import streamlit as st
from datetime import date
from core.queries import calcular_dashboard
from core.auth import check_login, logout

st.set_page_config(
    page_title="Control Operativo — Última Milla",
    page_icon="🚚",
    layout="wide",
)

check_login()

# ── CSS personalizado ────────────────────────────────────────────
st.markdown("""
<style>
.kpi-card { border-radius:12px; padding:20px 24px; margin:4px; text-align:center; }
.kpi-num  { font-size:3rem; font-weight:700; line-height:1; }
.kpi-lbl  { font-size:.9rem; margin-top:6px; opacity:.8; }
.verde    { background:#DCFCE7; color:#166534; border:1px solid #BBF7D0; }
.amarillo { background:#FEF9C3; color:#854D0E; border:1px solid #FDE68A; }
.rojo     { background:#FEE2E2; color:#991B1B; border:1px solid #FECACA; }
.badge-op { background:#DCFCE7; color:#166534; border-radius:99px;
            padding:2px 10px; font-size:.78rem; font-weight:600; }
.badge-ri { background:#FEF9C3; color:#854D0E; border-radius:99px;
            padding:2px 10px; font-size:.78rem; font-weight:600; }
.badge-no { background:#FEE2E2; color:#991B1B; border-radius:99px;
            padding:2px 10px; font-size:.78rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Cabecera ────────────────────────────────────────────────────
st.title("Control Operativo · Última Milla")

# ── Usuario en sidebar ───────────────────────────────────────────
with st.sidebar:
    usuario = st.session_state.get("usuario", "")
    st.markdown(f"👤 **{usuario}**")
    if st.button("Cerrar sesión", use_container_width=True):
        logout()
    st.divider()

# ── Selector de fecha ───────────────────────────────────────────
col_fecha, col_reset, _ = st.columns([2, 1, 6])
with col_fecha:
    fecha = st.date_input("Consultar estado para:", value=date.today(), key="fecha_dashboard")
with col_reset:
    st.write("")
    if st.button("Hoy"):
        st.session_state["fecha_dashboard"] = date.today()
        st.rerun()

st.divider()

# ── Cargar datos ────────────────────────────────────────────────
with st.spinner("Calculando estado de los servicios..."):
    try:
        estados = calcular_dashboard(fecha)
    except Exception as e:
        err = str(e)
        if "servicios" in err and "schema cache" in err:
            st.warning("Las tablas de la aplicación aún no están creadas en Supabase.")
            st.info("**Sigue estos pasos:**\n\n1. Ve a [supabase.com](https://supabase.com) → tu proyecto → **SQL Editor** → **New query**\n2. Abre el archivo `ultima-milla-streamlit/db/schema_nuevas_tablas.sql` con el Bloc de notas\n3. Copia todo el contenido y pégalo en el editor de Supabase\n4. Haz clic en **RUN** (botón verde)\n5. Vuelve aquí y recarga la página")
            st.stop()
        else:
            st.error(f"Error de conexión: {err}")
            st.info("Comprueba que `.streamlit/secrets.toml` tiene la URL y clave correctas de Supabase.")
            st.stop()

total       = len(estados)
operativos  = sum(1 for e in estados if e.estado == "OPERATIVO")
en_riesgo   = sum(1 for e in estados if e.estado == "EN_RIESGO")
no_op       = sum(1 for e in estados if e.estado == "NO_OPERATIVO")

# ── KPIs semáforo ───────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""
    <div class="kpi-card verde">
        <div class="kpi-num">{operativos}</div>
        <div class="kpi-lbl">Operativos</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="kpi-card amarillo">
        <div class="kpi-num">{en_riesgo}</div>
        <div class="kpi-lbl">En riesgo</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="kpi-card rojo">
        <div class="kpi-num">{no_op}</div>
        <div class="kpi-lbl">No operativos</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# ── Filtro por estado ───────────────────────────────────────────
filtro = st.radio(
    "Mostrar:",
    ["Todos", "Solo operativos", "Solo en riesgo", "Solo no operativos"],
    horizontal=True,
)
mapa_filtro = {
    "Todos": None,
    "Solo operativos": "OPERATIVO",
    "Solo en riesgo": "EN_RIESGO",
    "Solo no operativos": "NO_OPERATIVO",
}
estados_filtrados = [
    e for e in estados
    if mapa_filtro[filtro] is None or e.estado == mapa_filtro[filtro]
]

# ── Tabla de servicios ──────────────────────────────────────────
from core.queries import get_servicios, get_empleados
from core.fotos import get_fotos_marcas

servicios_map = {s["id"]: s for s in get_servicios()}
empleados_map = {e["id"]: e for e in get_empleados()}
fotos_marcas  = get_fotos_marcas()

BADGE = {
    "OPERATIVO":    '<span class="badge-op">Operativo</span>',
    "EN_RIESGO":    '<span class="badge-ri">En riesgo</span>',
    "NO_OPERATIVO": '<span class="badge-no">No operativo</span>',
}

if not estados_filtrados:
    st.info("No hay servicios que mostrar con el filtro seleccionado.")
else:
    st.write(f"**{len(estados_filtrados)} servicio(s)** para el **{fecha.strftime('%d/%m/%Y')}**")
    for e in sorted(estados_filtrados, key=lambda x: x.estado):
        srv = servicios_map.get(e.servicio_id, {})
        # Buscar foto del empleado efectivo
        emp_efectivo = next(
            (emp for emp in empleados_map.values()
             if f"{emp['nombre']} {emp['apellidos']}" == e.empleado_nombre), None
        )
        foto_emp = emp_efectivo.get("foto_url") if emp_efectivo else None
        # Foto de la marca del vehículo efectivo (buscar en vehiculos)
        from core.db import get_supabase
        veh_row = get_supabase().table("vehiculos").select("marca").eq(
            "matricula", e.vehiculo_matricula).limit(1).execute().data
        foto_veh = fotos_marcas.get(veh_row[0]["marca"]) if veh_row else None

        with st.container(border=True):
            col_foto_e, col_codigo, col_desc, col_emp, col_veh, col_estado = st.columns([0.5, 1.2, 2.5, 2, 1.8, 1.5])
            with col_foto_e:
                if foto_emp:
                    st.image(foto_emp, width=48)
                else:
                    st.markdown("<div style='font-size:32px;text-align:center'>👤</div>",
                                unsafe_allow_html=True)
            with col_codigo:
                st.markdown(f"**`{srv.get('codigo','—')}`**")
                zona = srv.get("zona")
                if zona:
                    st.caption(zona)
            with col_desc:
                st.write(srv.get("descripcion", "—"))
            with col_emp:
                icono = "🔄 " if e.es_sustitucion_empleado else ""
                st.write(f"{icono}{e.empleado_nombre}")
                if e.es_sustitucion_empleado:
                    st.caption("Sustitución activa")
            with col_veh:
                icono = "🔄 " if e.es_sustitucion_vehiculo else ""
                if foto_veh:
                    st.image(foto_veh, width=48)
                st.write(f"{icono}`{e.vehiculo_matricula}`")
                st.write(f"{e.vehiculo_marca_modelo}")
                if e.es_sustitucion_vehiculo:
                    st.caption("Sustitución activa")
            with col_estado:
                st.markdown(BADGE[e.estado], unsafe_allow_html=True)
            if e.motivos:
                with st.expander("Ver motivos"):
                    for m in e.motivos:
                        st.warning(m.descripcion, icon="⚠️")
