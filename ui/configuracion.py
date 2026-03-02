import streamlit as st
from datetime import date
from models.empleado import Empleado
from models.incidencia import TipoIncidencia
from repositories.empleado_repo import EmpleadoRepository
from repositories.festivo_repo import FestivoRepository
from repositories.incidencia_repo import IncidenciaRepository

_emp_repo = EmpleadoRepository()
_fest_repo = FestivoRepository()
_inc_repo = IncidenciaRepository()


def render_configuracion(usuario: Empleado, empleados: list[Empleado], anno: int) -> None:
    with st.expander("Configuración", expanded=False):
        tab1, tab2, tab3 = st.tabs([
            "Jornadas",
            f"Festivos {anno}",
            "Incidencias",
        ])

        with tab1:
            _tab_jornadas(usuario, empleados)

        with tab2:
            _tab_festivos(usuario, empleados, anno)

        with tab3:
            _tab_incidencias(usuario, empleados)


def _tab_jornadas(usuario: Empleado, empleados: list[Empleado]) -> None:
    st.markdown("##### Jornada semanal por empleado")
    with st.form("form_jornadas"):
        for emp in empleados:
            c1, c2 = st.columns([5, 1])
            c1.write(emp.apellidos_y_nombre)
            c2.number_input(
                "",
                min_value=0.0,
                max_value=60.0,
                step=0.5,
                value=emp.jornada_semanal,
                key=f"jornada_{emp.id}",
                label_visibility="collapsed",
            )
        if st.form_submit_button("Guardar jornadas"):
            for emp in empleados:
                nueva = st.session_state[f"jornada_{emp.id}"]
                _emp_repo.update_jornada(emp.id, nueva)
            st.success("Jornadas actualizadas correctamente.")
            st.rerun()


def _tab_festivos(usuario: Empleado, empleados: list[Empleado], anno: int) -> None:
    st.markdown("##### Añadir festivo local")
    with st.form("form_nuevo_festivo"):
        c1, c2 = st.columns([1, 2])
        fecha = c1.date_input("Fecha", key="fest_fecha", value=date(anno, 1, 1))
        desc = c2.text_input("Descripción", key="fest_desc")
        if st.form_submit_button("Añadir festivo"):
            if fecha.year != anno:
                st.error(f"La fecha debe pertenecer al año {anno}.")
            else:
                _fest_repo.create_festivo(fecha, anno, desc, usuario.id)
                st.success(f"Festivo añadido: {fecha.isoformat()}")
                st.rerun()

    festivos = _fest_repo.get_locales(anno, usuario.id)
    if not festivos:
        st.info("No hay festivos locales definidos para este año.")
        return

    for fest in festivos:
        with st.expander(f"{fest.fecha.strftime('%d/%m/%Y')} — {fest.descripcion or '(sin descripción)'}"):
            asignados = _fest_repo.get_ids_asignados(fest.id)
            with st.form(f"form_fest_{fest.id}"):
                seleccionados = []
                for emp in empleados:
                    checked = emp.id in asignados
                    if st.checkbox(emp.apellidos_y_nombre, value=checked, key=f"f_{fest.id}_{emp.id}"):
                        seleccionados.append(emp.id)
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Guardar asignaciones"):
                    _fest_repo.guardar_asignaciones(fest.id, seleccionados)
                    st.success("Asignaciones guardadas.")
                    st.rerun()
                if c2.form_submit_button("Eliminar festivo", type="secondary"):
                    _fest_repo.delete_festivo(fest.id)
                    st.success("Festivo eliminado.")
                    st.rerun()


def _tab_incidencias(usuario: Empleado, empleados: list[Empleado]) -> None:
    st.markdown("##### Registrar incidencia")
    with st.form("form_incidencia"):
        emp_nombres = [e.apellidos_y_nombre for e in empleados]
        emp_sel = st.selectbox("Empleado", emp_nombres, key="inc_emp")
        emp_id = next(e.id for e in empleados if e.apellidos_y_nombre == emp_sel)

        tipo = st.selectbox(
            "Tipo",
            [t.value for t in TipoIncidencia],
            key="inc_tipo",
        )

        c1, c2 = st.columns(2)
        ini = c1.date_input("Fecha inicio", key="inc_ini")
        fin = c2.date_input("Fecha fin", key="inc_fin")
        desc = st.text_input("Descripción (opcional)", key="inc_desc")

        if st.form_submit_button("Guardar incidencia"):
            if fin < ini:
                st.error("La fecha de fin no puede ser anterior a la de inicio.")
            else:
                _inc_repo.create(
                    empleado_id=emp_id,
                    tipo=TipoIncidencia(tipo),
                    fecha_inicio=ini,
                    fecha_fin=fin,
                    descripcion=desc,
                    created_by=usuario.id,
                )
                st.success("Incidencia registrada correctamente.")
                st.rerun()
