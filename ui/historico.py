import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from models.empleado import Empleado
from repositories.historico_repo import HistoricoRepository

MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

_hist_repo = HistoricoRepository()


def _label_mes(anno: int, mes: int) -> str:
    return f"{MESES_ES.get(mes, mes)}/{str(anno)[2:]}"


def render_historico(
    usuario: Empleado,
    resumen_actual: list[dict],
    anno: int,
    mes: int,
    mostrar_todos: bool = False,
) -> None:
    st.divider()
    st.markdown('<a name="historico-evolucion"></a>', unsafe_allow_html=True)
    st.subheader("Histórico y evolución")

    responsable_id = "global" if mostrar_todos else usuario.id

    # ── Guardar periodo actual ────────────────────────────────────────────────
    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        if st.button(
            f"Guardar {MESES_ES.get(mes, mes)}/{anno}",
            use_container_width=True,
            type="primary",
            key=f"btn_guardar_hist_{responsable_id}",
        ):
            if resumen_actual:
                _hist_repo.guardar_resumen(responsable_id, anno, mes, resumen_actual)
                st.success(f"Periodo {MESES_ES.get(mes, mes)}/{anno} guardado.")
                st.rerun()
            else:
                st.warning("No hay datos en el resumen actual.")
    with col_info:
        st.caption("Guarda el resumen del mes cargado para incluirlo en las gráficas de evolución.")

    # ── Archivos Excel guardados ──────────────────────────────────────────────
    with st.expander("Archivos Excel guardados", expanded=False):
        _render_archivos(usuario, responsable_id, anno, mes, resumen_actual)

    # ── Gráficas de evolución ─────────────────────────────────────────────────
    historico = _hist_repo.get_historico(responsable_id)
    if not historico:
        st.info("Guarda al menos un periodo para ver las gráficas de evolución.")
        return

    df = pd.DataFrame(historico)
    df["label"] = df.apply(lambda r: _label_mes(int(r["anno"]), int(r["mes"])), axis=1)
    df["label_sort"] = df["anno"].astype(str) + df["mes"].astype(str).str.zfill(2)
    df = df.sort_values("label_sort")

    _render_graficas_evolucion(df, mostrar_todos)


def _render_archivos(
    usuario: Empleado,
    responsable_id: str,
    anno: int,
    mes: int,
    resumen_actual: list[dict],
) -> None:
    archivos = _hist_repo.listar_excels(responsable_id)

    col_sub, _ = st.columns([3, 4])
    with col_sub:
        if st.button(
            f"Guardar Excel {MESES_ES.get(mes, mes)}/{anno} en almacén",
            use_container_width=True,
            key=f"btn_subir_excel_{responsable_id}",
        ):
            if "upload_excel" in st.session_state and st.session_state["upload_excel"] is not None:
                archivo = st.session_state["upload_excel"]
                ok = _hist_repo.subir_excel(responsable_id, anno, mes, archivo.getvalue())
                if ok:
                    st.success("Excel guardado en el almacén.")
                    st.rerun()
                else:
                    st.error("No se pudo guardar el Excel. Verifica que el bucket 'fichajes' existe en Supabase Storage.")
            else:
                st.warning("Sube un Excel primero.")

    if not archivos:
        st.info("No hay archivos guardados.")
        return

    st.markdown(f"**{len(archivos)} archivo{'s' if len(archivos) != 1 else ''} guardado{'s' if len(archivos) != 1 else ''}**")

    for archivo in sorted(archivos, key=lambda x: x.get("name", ""), reverse=True):
        nombre = archivo.get("name", "")
        if not nombre:
            continue
        tamaño = archivo.get("metadata", {}).get("size", 0)
        tamaño_str = f"{round(tamaño / 1024)} KB" if tamaño else ""

        c1, c2, c3 = st.columns([4, 2, 1])
        c1.markdown(f"📄 **{nombre}** {f'`{tamaño_str}`' if tamaño_str else ''}")

        with c2:
            datos = _hist_repo.descargar_excel(responsable_id, nombre)
            if datos:
                st.download_button(
                    label="Descargar",
                    data=datos,
                    file_name=nombre,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"dl_{responsable_id}_{nombre}",
                )

        with c3:
            if st.button("🗑", key=f"del_{responsable_id}_{nombre}", help="Borrar archivo"):
                ok = _hist_repo.borrar_excel(responsable_id, nombre)
                if ok:
                    st.success("Archivo borrado.")
                    st.rerun()


def _render_graficas_evolucion(df: pd.DataFrame, mostrar_todos: bool) -> None:
    st.markdown("#### Evolución histórica")

    # ── Métricas globales por mes ─────────────────────────────────────────────
    resumen_mes = (
        df.groupby(["label", "label_sort"])
        .agg(
            total=("laborables", "count"),
            fichados_ok=("sin_fichar", lambda x: (x == 0).sum()),
            sin_fichar=("sin_fichar", lambda x: (x > 0).sum()),
            con_error=("errores", lambda x: (x > 0).sum()),
        )
        .reset_index()
        .sort_values("label_sort")
    )

    resumen_mes["pct_ok"] = (resumen_mes["fichados_ok"] / resumen_mes["total"] * 100).round(1)
    resumen_mes["pct_sin"] = (resumen_mes["sin_fichar"] / resumen_mes["total"] * 100).round(1)
    resumen_mes["pct_err"] = (resumen_mes["con_error"] / resumen_mes["total"] * 100).round(1)

    # Gráfica 1: % fichaje OK / sin fichar / con error
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=resumen_mes["label"], y=resumen_mes["pct_ok"],
        name="Fichaje OK", marker_color="#28a745",
        text=resumen_mes["pct_ok"].astype(str) + "%", textposition="inside",
    ))
    fig1.add_trace(go.Bar(
        x=resumen_mes["label"], y=resumen_mes["pct_sin"],
        name="Sin fichar", marker_color="#fd7e14",
        text=resumen_mes["pct_sin"].astype(str) + "%", textposition="inside",
    ))
    fig1.add_trace(go.Bar(
        x=resumen_mes["label"], y=resumen_mes["pct_err"],
        name="Con error", marker_color="#dc3545",
        text=resumen_mes["pct_err"].astype(str) + "%", textposition="inside",
    ))
    fig1.update_layout(
        barmode="group",
        title="% Empleados por estado de fichaje (por mes)",
        xaxis_title="Mes",
        yaxis_title="%",
        yaxis_range=[0, 110],
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=380,
        margin=dict(t=60, b=40),
        plot_bgcolor="#f8f9fa",
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Gráfica 2: evolución horas reales vs objetivo
    horas_mes = (
        df.groupby(["label", "label_sort"])
        .agg(horas_reales=("horas_reales", "sum"), objetivo=("objetivo", "sum"))
        .reset_index()
        .sort_values("label_sort")
    )
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=horas_mes["label"], y=horas_mes["objetivo"],
        mode="lines+markers", name="Objetivo",
        line=dict(color="#1a3d6e", dash="dash"), marker=dict(size=7),
    ))
    fig2.add_trace(go.Scatter(
        x=horas_mes["label"], y=horas_mes["horas_reales"],
        mode="lines+markers", name="Horas reales",
        line=dict(color="#2e6da4"), marker=dict(size=7),
        fill="tonexty", fillcolor="rgba(46,109,164,0.08)",
    ))
    fig2.update_layout(
        title="Evolución horas totales: realizadas vs objetivo",
        xaxis_title="Mes",
        yaxis_title="Horas",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=340,
        margin=dict(t=60, b=40),
        plot_bgcolor="#f8f9fa",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Gráfica 3: desglose por empleado si no es vista global
    if not mostrar_todos:
        empleados_unicos = df["nombre"].unique().tolist()
        sel = st.multiselect(
            "Filtrar empleados para ver su evolución individual",
            options=empleados_unicos,
            default=empleados_unicos[:5] if len(empleados_unicos) > 5 else empleados_unicos,
            key="hist_sel_empleados",
        )
        if sel:
            df_sel = df[df["nombre"].isin(sel)].sort_values("label_sort")
            fig3 = px.line(
                df_sel, x="label", y="sin_fichar", color="nombre",
                title="Días sin fichar por empleado (evolución)",
                labels={"label": "Mes", "sin_fichar": "Días sin fichar", "nombre": "Empleado"},
                markers=True,
                height=360,
            )
            fig3.update_layout(
                plot_bgcolor="#f8f9fa",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=60, b=40),
            )
            st.plotly_chart(fig3, use_container_width=True)

    # Gráfica 4: comparativa global por meses guardados
    _render_comparativa_global(df)


def _render_comparativa_global(df: pd.DataFrame) -> None:
    """Gráfica comparativa de métricas globales agregadas por mes guardado."""
    if df.empty:
        return

    st.markdown("#### Comparativa global por mes")
    st.caption("Totales agregados de todos los empleados en cada mes guardado.")

    meses_ord = (
        df[["label", "label_sort"]]
        .drop_duplicates()
        .sort_values("label_sort")["label"]
        .tolist()
    )

    agg = (
        df.groupby(["label", "label_sort"])
        .agg(
            empleados=("nombre", "nunique"),
            laborables_total=("laborables", "sum"),
            fichados_total=("fichados", "sum"),
            errores_total=("errores", "sum"),
            sin_fichar_total=("sin_fichar", "sum"),
            horas_reales_total=("horas_reales", "sum"),
            objetivo_total=("objetivo", "sum"),
        )
        .reset_index()
        .sort_values("label_sort")
    )

    agg["pct_ok"] = (
        (agg["fichados_total"] - agg["errores_total"]).clip(lower=0)
        / agg["laborables_total"].replace(0, 1) * 100
    ).round(1)
    agg["pct_sin"] = (agg["sin_fichar_total"] / agg["laborables_total"].replace(0, 1) * 100).round(1)
    agg["pct_err"] = (agg["errores_total"] / agg["laborables_total"].replace(0, 1) * 100).round(1)
    agg["pct_horas"] = (agg["horas_reales_total"] / agg["objetivo_total"].replace(0, 1) * 100).round(1)

    tab1, tab2 = st.tabs(["Cumplimiento (%)", "Horas realizadas vs objetivo"])

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg["label"], y=agg["pct_ok"],
            name="Fichaje OK", marker_color="#28a745",
            text=agg["pct_ok"].astype(str) + "%", textposition="outside",
        ))
        fig.add_trace(go.Bar(
            x=agg["label"], y=agg["pct_sin"],
            name="Sin fichar", marker_color="#fd7e14",
            text=agg["pct_sin"].astype(str) + "%", textposition="outside",
        ))
        fig.add_trace(go.Bar(
            x=agg["label"], y=agg["pct_err"],
            name="Con error", marker_color="#dc3545",
            text=agg["pct_err"].astype(str) + "%", textposition="outside",
        ))
        fig.update_layout(
            barmode="group",
            title="% global de cumplimiento por mes",
            xaxis_title="Mes",
            yaxis=dict(title="%", range=[0, 115]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400,
            margin=dict(t=60, b=40),
            plot_bgcolor="#f8f9fa",
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        for i, row in agg.iterrows():
            with [col1, col2, col3][i % 3]:
                st.metric(
                    label=row["label"],
                    value=f"{row['pct_ok']}% OK",
                    delta=f"{row['empleados']} empleados",
                )

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=agg["label"], y=agg["objetivo_total"],
            mode="lines+markers", name="Objetivo total",
            line=dict(color="#1a3d6e", dash="dash"), marker=dict(size=8),
        ))
        fig2.add_trace(go.Scatter(
            x=agg["label"], y=agg["horas_reales_total"],
            mode="lines+markers", name="Horas reales",
            line=dict(color="#2e6da4", width=2), marker=dict(size=8),
            fill="tonexty", fillcolor="rgba(46,109,164,0.1)",
        ))
        fig2.add_trace(go.Bar(
            x=agg["label"], y=agg["pct_horas"],
            name="% cumplimiento horas",
            marker_color="rgba(40,167,69,0.3)",
            yaxis="y2",
            text=agg["pct_horas"].astype(str) + "%", textposition="outside",
        ))
        fig2.update_layout(
            title="Horas globales realizadas vs objetivo por mes",
            xaxis_title="Mes",
            yaxis=dict(title="Horas totales"),
            yaxis2=dict(title="% cumplimiento", overlaying="y", side="right", range=[0, 130], showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=420,
            margin=dict(t=60, b=40),
            plot_bgcolor="#f8f9fa",
        )
        st.plotly_chart(fig2, use_container_width=True)
