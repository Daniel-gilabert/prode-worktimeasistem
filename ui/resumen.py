import streamlit as st
import pandas as pd
import unicodedata
from models.empleado import Empleado
from services.calculo_service import CalculoService
from services.informe_pdf_service import InformePDFService
from services.informe_excel_service import InformeExcelService
from repositories.empleado_repo import EmpleadoRepository
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

    pdf_svc = InformePDFService(logo_path=LOGO_PATH)
    xls_svc = InformeExcelService()
    emp_repo = EmpleadoRepository()

    # ── Claves normalizadas (exacta + sorted) ─────────────────────────────────
    claves_excel_exactas = set(df_fichajes["clave"].dropna().unique()) if "clave" in df_fichajes.columns else set()
    claves_excel_sorted  = set(df_fichajes["clave_sorted"].dropna().unique()) if "clave_sorted" in df_fichajes.columns else set()

    def _tiene_datos(e: Empleado) -> bool:
        ce = _limpiar(e.apellidos_y_nombre)
        cs = _clave_sorted(e.apellidos_y_nombre)
        return ce in claves_excel_exactas or cs in claves_excel_sorted

    sin_datos       = [e for e in empleados if not _tiene_datos(e)]
    con_datos_emps  = [e for e in empleados if _tiene_datos(e)]

    # Nombres en Excel no en BD (usando sorted para detectar correctamente)
    claves_bd_sorted = {_clave_sorted(e.apellidos_y_nombre) for e in empleados}
    nuevos_en_excel  = sorted(claves_excel_sorted - claves_bd_sorted)

    # ── Alerta: nuevos en Excel no están en BD ────────────────────────────────
    if nuevos_en_excel:
        with st.expander(
            f"Empleados nuevos en el Excel no registrados en BD ({len(nuevos_en_excel)})",
            expanded=False,
        ):
            st.caption("Puedes añadirlos a tu grupo o ignorarlos.")
            for nombre_excel in nuevos_en_excel:
                col_n, col_j, col_btn, col_skip = st.columns([4, 2, 2, 1])
                col_n.markdown(f"**{nombre_excel.title()}**")
                jornada_nueva = col_j.number_input(
                    "Jornada (h/sem)",
                    min_value=1.0,
                    max_value=40.0,
                    value=38.5,
                    step=0.5,
                    key=f"jornada_nuevo_{nombre_excel}",
                    label_visibility="collapsed",
                )
                with col_btn:
                    if st.button(
                        "Añadir",
                        key=f"btn_nuevo_{nombre_excel}",
                        use_container_width=True,
                        type="primary",
                    ):
                        responsable_id = usuario.id if usuario else ""
                        emp_repo.crear_empleado(
                            apellidos_y_nombre=nombre_excel.title(),
                            responsable_id=responsable_id,
                            jornada_semanal=jornada_nueva,
                        )
                        st.success(f"'{nombre_excel.title()}' añadido.")
                        st.rerun()
                with col_skip:
                    st.button("—", key=f"btn_skip_{nombre_excel}", help="No añadir", disabled=True)

    # ── Resultados normales ───────────────────────────────────────────────────
    resultados = _calc.calcular_resumen_global(
        empleados, df_fichajes, mapa_festivos, mapa_incidencias, anno, mes
    )

    # Añadir detalle diario a cada resultado para el PDF
    emp_por_id = {e.id: e for e in empleados}
    for d in resultados:
        emp_obj = emp_por_id.get(d["id"])
        if emp_obj:
            festivos_emp = mapa_festivos.get(emp_obj.id, set())
            incidencias_emp = mapa_incidencias.get(emp_obj.id, set())
            d["dias"] = _calc.calcular_detalle_diario(
                emp_obj, df_fichajes, festivos_emp, incidencias_emp, anno, mes
            )

    for d in resultados:
        if d["sin_fichar"] == 0:
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
        st.markdown(
            f"**{len(sin_datos)} empleado(s) sin datos en el Excel de este mes:**",
        )
        for e in sin_datos:
            st.markdown(
                f"""
                <div style="
                    background:#e9ecef;padding:8px 14px;border-radius:8px;
                    font-size:13px;line-height:1.6;margin-top:4px;color:#6c757d;
                ">
                    <strong>{e.apellidos_y_nombre}</strong>
                    &nbsp;|&nbsp; Sin datos este mes
                </div>
                """,
                unsafe_allow_html=True,
            )

    return resultados
