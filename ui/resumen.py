import streamlit as st
import pandas as pd
import unicodedata
from models.empleado import Empleado
from services.calculo_service import CalculoService
from services.informe_pdf_service import InformePDFService
from services.informe_excel_service import InformeExcelService
from repositories.empleado_repo import EmpleadoRepository
from repositories.incidencia_repo import IncidenciaRepository
from repositories.ignorados_repo import IgnoradosRepository
from datetime import date
import os

_calc = CalculoService()

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

LOGO_PATH = "assets/logo-prode.png" if os.path.exists("assets/logo-prode.png") else None


def _limpiar(txt) -> str:
    if not txt:
        return ""
    txt = str(txt).strip().upper()
    txt = unicodedata.normalize("NFD", txt)
    txt = txt.encode("ascii", "ignore").decode("utf-8")
    return " ".join(txt.split())


def _clave_sorted(txt) -> str:
    return " ".join(sorted(_limpiar(txt).split()))


def render_resumen(
    empleados: list[Empleado],
    df_fichajes: pd.DataFrame,
    mapa_festivos: dict[str, set[date]],
    mapa_incidencias: dict[str, set[date]],
    anno: int,
    mes: int,
    usuario: Empleado | None = None,
) -> list[dict]:
    nombre_mes = MESES_ES.get(mes, str(mes))
    st.subheader(f"Resumen mensual — {nombre_mes} {anno}")

    if not empleados:
        st.warning("No hay empleados asignados.")
        return []

    pdf_svc      = InformePDFService(logo_path=LOGO_PATH)
    xls_svc      = InformeExcelService()
    emp_repo     = EmpleadoRepository()
    inc_repo     = IncidenciaRepository()
    ign_repo     = IgnoradosRepository()
    mapa_detalle_inc = inc_repo.get_detalle_por_empleado()

    responsable_id = usuario.id if usuario else ""
    dept_usuario   = (usuario.departamento or "") if usuario else ""
    ignorados = ign_repo.get_por_responsable(responsable_id) if responsable_id else set()

    # ── Claves normalizadas (exacta + sorted) ─────────────────────────────────
    claves_excel_exactas = set(df_fichajes["clave"].dropna().unique()) if "clave" in df_fichajes.columns else set()
    claves_excel_sorted  = set(df_fichajes["clave_sorted"].dropna().unique()) if "clave_sorted" in df_fichajes.columns else set()

    def _tiene_datos(e: Empleado) -> bool:
        ce = _limpiar(e.apellidos_y_nombre)
        cs = _clave_sorted(e.apellidos_y_nombre)
        return ce in claves_excel_exactas or cs in claves_excel_sorted

    sin_datos      = [e for e in empleados if not _tiene_datos(e)]
    con_datos_emps = [e for e in empleados if _tiene_datos(e)]

    # Buscar en TODA la BD (incluye otros departamentos) para detectar duplicados
    todos_bd = emp_repo.get_todos_con_inactivos()
    mapa_bd_por_clave: dict[str, Empleado] = {}
    for e in todos_bd:
        mapa_bd_por_clave[_clave_sorted(e.apellidos_y_nombre)] = e

    # Nombres en Excel no en el grupo actual (excluir ignorados)
    claves_bd_sorted_grupo = {_clave_sorted(e.apellidos_y_nombre) for e in empleados}
    nuevos_en_excel = sorted(
        cs for cs in claves_excel_sorted - claves_bd_sorted_grupo
        if cs not in ignorados
    )

    # Empleados solo para semáforo esta sesión (no guardados en BD)
    semaforo_temporal: set[str] = st.session_state.get("semaforo_temporal", set())

    # ── Alerta: nuevos en Excel no están en el grupo actual ───────────────────
    if nuevos_en_excel:
        with st.expander(
            f"Empleados nuevos en el Excel no registrados en tu grupo ({len(nuevos_en_excel)})",
            expanded=False,
        ):
            st.caption(
                "Estos empleados aparecen en el Excel pero no están en tu grupo. "
                "Si ya existen en la BD se vincularán sin duplicar."
            )
            for cs in nuevos_en_excel:
                existe_en_bd = mapa_bd_por_clave.get(cs)
                col_n, col_j, col_add, col_tmp, col_nope = st.columns([4, 2, 2, 2, 2])
                col_n.markdown(
                    f"**{cs.title()}**"
                    + (f"<br><span style='font-size:11px;color:#6c757d'>Ya existe en BD</span>" if existe_en_bd else "")
                    , unsafe_allow_html=True
                )

                jornada_nueva = col_j.number_input(
                    "h/sem",
                    min_value=1.0, max_value=40.0, value=38.5, step=0.5,
                    key=f"jornada_nuevo_{cs}",
                    label_visibility="collapsed",
                    disabled=bool(existe_en_bd),
                )

                # Botón principal: Vincular (si existe) o Añadir (si es nuevo)
                with col_add:
                    if existe_en_bd:
                        if st.button("Vincular a mi grupo", key=f"btn_vincular_{cs}",
                                     use_container_width=True, type="primary"):
                            emp_repo.vincular_a_responsable(
                                existe_en_bd.id, responsable_id, dept_usuario
                            )
                            st.success(f"'{cs.title()}' vinculado a tu grupo.")
                            st.rerun()
                    else:
                        if st.button("Añadir a BD", key=f"btn_nuevo_{cs}",
                                     use_container_width=True, type="primary"):
                            emp_repo.crear_empleado(
                                apellidos_y_nombre=cs.title(),
                                responsable_id=responsable_id,
                                jornada_semanal=jornada_nueva,
                                departamento=dept_usuario,
                            )
                            st.success(f"'{cs.title()}' añadido.")
                            st.rerun()

                # Solo semáforo esta sesión
                with col_tmp:
                    if cs in semaforo_temporal:
                        st.caption("✓ En semáforo")
                    else:
                        if st.button("Solo semáforo", key=f"btn_tmp_{cs}",
                                     use_container_width=True):
                            semaforo_temporal.add(cs)
                            st.session_state["semaforo_temporal"] = semaforo_temporal
                            st.rerun()

                # No es mi departamento
                with col_nope:
                    confirm_key = f"confirm_ignorar_{cs}"
                    if st.session_state.get(confirm_key):
                        col_si, col_no = st.columns(2)
                        if col_si.button("Sí, ocultar", key=f"si_ignorar_{cs}", use_container_width=True):
                            ign_repo.ignorar(responsable_id, cs)
                            semaforo_temporal.discard(cs)
                            st.session_state["semaforo_temporal"] = semaforo_temporal
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                        if col_no.button("Cancelar", key=f"no_ignorar_{cs}", use_container_width=True):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    else:
                        if st.button("No es mi dpto.", key=f"btn_ignorar_{cs}",
                                     use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()

    # Añadir temporales al listado de empleados para el cálculo
    for cs in list(semaforo_temporal):
        if cs not in claves_bd_sorted_grupo:
            emp_tmp = Empleado(
                id=f"tmp_{cs}",
                apellidos_y_nombre=cs.title(),
                email="",
                activo=True,
                jornada_semanal=38.5,
                responsable_id=responsable_id,
                departamento=dept_usuario,
            )
            empleados = list(empleados) + [emp_tmp]

    # ── Resultados normales ───────────────────────────────────────────────────
    resultados = _calc.calcular_resumen_global(
        empleados, df_fichajes, mapa_festivos, mapa_incidencias, anno, mes
    )

    # Marcar empleados sin datos en el Excel
    ids_sin_datos = {e.id for e in sin_datos}
    for d in resultados:
        d["sin_datos_excel"] = d["id"] in ids_sin_datos

    # Añadir detalle diario a cada resultado para el PDF
    emp_por_id = {e.id: e for e in empleados}
    for d in resultados:
        emp_obj = emp_por_id.get(d["id"])
        if emp_obj:
            festivos_emp    = mapa_festivos.get(emp_obj.id, set())
            incidencias_emp = mapa_incidencias.get(emp_obj.id, set())
            d["dias"] = _calc.calcular_detalle_diario(
                emp_obj, df_fichajes, festivos_emp, incidencias_emp, anno, mes,
                detalle_incidencia=mapa_detalle_inc.get(emp_obj.id),
            )

    # Mostrar solo empleados CON datos en el resumen visual
    resultados_con_datos = [d for d in resultados if not d.get("sin_datos_excel")]

    for d in resultados_con_datos:
        if d.get("mes_completo_incidencia"):
            color = "#cce5ff"
        elif d["sin_fichar"] == 0:
            color = "#d4edda"
        elif d["sin_fichar"] < 3:
            color = "#ffe5b4"
        else:
            color = "#f8d7da"

        diferencia_str = f"+{d['diferencia']}" if d["diferencia"] > 0 else str(d["diferencia"])
        nombre_safe = d["nombre"].replace(" ", "_")

        col_info, col_pdf, col_xls = st.columns([8, 1, 1])

        with col_info:
            st.markdown(
                f"""
                <div style="
                    background:{color};padding:10px 14px;border-radius:8px;
                    font-size:13px;line-height:1.6;margin-top:4px;
                ">
                    <strong>{d['nombre']}</strong>
                    &nbsp;|&nbsp; Laborables: <strong>{d['laborables']}</strong>
                    &nbsp;|&nbsp; Fichados: <strong>{d['fichados']}</strong>
                    &nbsp;|&nbsp; Errores: <strong>{d['errores']}</strong>
                    &nbsp;|&nbsp; Sin fichar: <strong>{d['sin_fichar']}</strong>
                    &nbsp;|&nbsp; Objetivo: <strong>{d['objetivo']} h</strong>
                    &nbsp;|&nbsp; Horas reales: <strong>{d['horas_reales']} h</strong>
                    &nbsp;|&nbsp; Diferencia: <strong>{diferencia_str} h</strong>
                    &nbsp;|&nbsp; Extra: <strong>{d['horas_extra']} h</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_pdf:
            pdf_bytes = pdf_svc.generar_pdf_individual(d, mes, anno)
            st.download_button(
                label="PDF",
                data=pdf_bytes,
                file_name=f"{nombre_safe}_{nombre_mes}_{anno}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"pdf_inline_{d['id']}",
            )

        with col_xls:
            xls_bytes = xls_svc.generar_excel_individual(d, mes, anno)
            st.download_button(
                label="XLS",
                data=xls_bytes,
                file_name=f"{nombre_safe}_{nombre_mes}_{anno}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"xls_inline_{d['id']}",
            )

    # ── Empleados en BD sin datos en el Excel ─────────────────────────────────
    if sin_datos:
        st.divider()
        with st.expander(
            f"Empleados sin datos en el Excel de este mes ({len(sin_datos)})",
            expanded=False,
        ):
            st.caption(
                "Estos empleados están en tu BD pero no tienen fichajes en el Excel cargado. "
                "Puedes eliminarlos si ya no pertenecen a tu equipo."
            )
            for e in sin_datos:
                col_nombre, col_del = st.columns([7, 2])
                col_nombre.markdown(
                    f'<div style="background:#e9ecef;padding:8px 14px;border-radius:8px;'
                    f'font-size:13px;color:#6c757d;">'
                    f'<strong>{e.apellidos_y_nombre}</strong>'
                    f'&nbsp;·&nbsp; Sin datos este mes</div>',
                    unsafe_allow_html=True,
                )
                with col_del:
                    confirm_key = f"confirm_del_{e.id}"
                    if st.session_state.get(confirm_key):
                        col_si2, col_no2 = st.columns(2)
                        if col_si2.button("Sí, eliminar", key=f"si_del_{e.id}", use_container_width=True, type="primary"):
                            emp_repo.eliminar_empleado(e.id)
                            st.session_state.pop(confirm_key, None)
                            st.success(f"'{e.apellidos_y_nombre}' eliminado.")
                            st.rerun()
                        if col_no2.button("Cancelar", key=f"no_del_{e.id}", use_container_width=True):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    else:
                        if st.button(
                            "Eliminar de BD",
                            key=f"btn_del_{e.id}",
                            use_container_width=True,
                        ):
                            st.session_state[confirm_key] = True
                            st.rerun()

    return resultados
