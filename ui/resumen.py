import streamlit as st
import pandas as pd
from models.empleado import Empleado
from services.calculo_service import CalculoService
from datetime import date

_calc = CalculoService()

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def render_resumen(
    empleados: list[Empleado],
    df_fichajes: pd.DataFrame,
    mapa_festivos: dict[str, set[date]],
    mapa_incidencias: dict[str, set[date]],
    anno: int,
    mes: int,
) -> list[dict]:
    nombre_mes = MESES_ES.get(mes, str(mes))
    st.subheader(f"Resumen mensual — {nombre_mes} {anno}")

    if not empleados:
        st.warning("No hay empleados asignados.")
        return []

    resultados = _calc.calcular_resumen_global(
        empleados, df_fichajes, mapa_festivos, mapa_incidencias, anno, mes
    )

    for d in resultados:
        if d["sin_fichar"] == 0:
            color = "#d4edda"
        elif d["sin_fichar"] < 3:
            color = "#ffe5b4"
        else:
            color = "#f8d7da"

        diferencia_str = f"+{d['diferencia']}" if d["diferencia"] > 0 else str(d["diferencia"])

        st.markdown(
            f"""
            <div style="
                background:{color};
                padding:10px 14px;
                border-radius:8px;
                margin-bottom:6px;
                font-size:13px;
                line-height:1.6;
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

    return resultados
