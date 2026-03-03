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

C_VERDE   = "#28a745"
C_AZUL    = "#17a2b8"
C_NARANJA = "#fd7e14"
C_ROJO    = "#dc3545"
C_PRODE   = "#1a3d6e"


def _label_mes(anno: int, mes: int) -> str:
    return f"{MESES_ES.get(mes, mes)}/{str(anno)[2:]}"


def _clasificar_semaforo(row) -> str:
    if row["sin_fichar"] == 0 and row["errores"] == 0:
        return "Verde (completo)"
    elif row["sin_fichar"] == 0 and row["errores"] > 0:
        return "Azul (errores)"
    elif 0 < row["sin_fichar"] <= 2:
        return "Naranja (1-2 días)"
    else:
        return "Rojo (≥3 días)"


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

    # ── Guardar periodo ───────────────────────────────────────────────────────
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
        st.caption("Guarda el resumen del mes para incluirlo en las gráficas de evolución.")

    # ── Archivos Excel ────────────────────────────────────────────────────────
    with st.expander("Archivos Excel guardados", expanded=False):
        _render_archivos(usuario, responsable_id, anno, mes, resumen_actual)

    # ── Cargar histórico ──────────────────────────────────────────────────────
    historico = _hist_repo.get_historico(responsable_id)
    if not historico:
        st.info("Guarda al menos un periodo para ver las gráficas de evolución.")
        return

    df = pd.DataFrame(historico)
    df["label"]      = df.apply(lambda r: _label_mes(int(r["anno"]), int(r["mes"])), axis=1)
    df["label_sort"] = df["anno"].astype(str) + df["mes"].astype(str).str.zfill(2)
    df["horas_extra"] = pd.to_numeric(df.get("horas_extra", 0), errors="coerce").fillna(0)
    df = df.sort_values("label_sort")

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tabs = ["📊 Evolución fichaje", "⏱ Horas y horas extra"]
    if mostrar_todos:
        tabs.append("👥 Por responsable")

    tab_list = st.tabs(tabs)

    with tab_list[0]:
        _tab_semaforo(df, mostrar_todos)

    with tab_list[1]:
        _tab_horas(df, mostrar_todos)

    if mostrar_todos and len(tab_list) > 2:
        with tab_list[2]:
            _tab_por_responsable(df)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — EVOLUCIÓN FICHAJE (4 variables semáforo)
# ═════════════════════════════════════════════════════════════════════════════
def _tab_semaforo(df: pd.DataFrame, mostrar_todos: bool) -> None:
    df = df.copy()
    df["semaforo"] = df.apply(_clasificar_semaforo, axis=1)

    resumen_mes = (
        df.groupby(["label", "label_sort"])
        .agg(
            total=("nombre", "count"),
            verde=(  "semaforo", lambda x: (x == "Verde (completo)").sum()),
            azul=(   "semaforo", lambda x: (x == "Azul (errores)").sum()),
            naranja=("semaforo", lambda x: (x == "Naranja (1-2 días)").sum()),
            rojo=(   "semaforo", lambda x: (x == "Rojo (≥3 días)").sum()),
        )
        .reset_index()
        .sort_values("label_sort")
    )

    for col in ["verde", "azul", "naranja", "rojo"]:
        resumen_mes[f"pct_{col}"] = (resumen_mes[col] / resumen_mes["total"] * 100).round(1)

    # Gráfica apilada 100% con las 4 variables
    fig = go.Figure()
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_verde"],
        name="Verde — Fichaje completo", marker_color=C_VERDE,
        text=resumen_mes["pct_verde"].astype(str)+"%", textposition="inside"))
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_azul"],
        name="Azul — Con errores", marker_color=C_AZUL,
        text=resumen_mes["pct_azul"].astype(str)+"%", textposition="inside"))
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_naranja"],
        name="Naranja — 1-2 días sin fichar", marker_color=C_NARANJA,
        text=resumen_mes["pct_naranja"].astype(str)+"%", textposition="inside"))
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_rojo"],
        name="Rojo — ≥3 días sin fichar", marker_color=C_ROJO,
        text=resumen_mes["pct_rojo"].astype(str)+"%", textposition="inside"))
    fig.update_layout(
        barmode="stack",
        title="Distribución semáforo por mes (% empleados)",
        xaxis_title="Mes", yaxis=dict(title="%", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400, margin=dict(t=70, b=40), plot_bgcolor="#f8f9fa",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Métricas del último mes guardado
    ultimo = resumen_mes.iloc[-1]
    st.caption(f"Último periodo guardado: **{ultimo['label']}** — {int(ultimo['total'])} empleados")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Fichaje completo", f"{int(ultimo['verde'])}  ({ultimo['pct_verde']}%)")
    c2.metric("🔵 Con errores",      f"{int(ultimo['azul'])}  ({ultimo['pct_azul']}%)")
    c3.metric("🟠 1-2 días",         f"{int(ultimo['naranja'])}  ({ultimo['pct_naranja']}%)")
    c4.metric("🔴 ≥3 días",          f"{int(ultimo['rojo'])}  ({ultimo['pct_rojo']}%)")

    # Evolución individual (solo vista responsable)
    if not mostrar_todos:
        st.markdown("---")
        empleados_unicos = sorted(df["nombre"].unique().tolist())
        sel = st.multiselect(
            "Ver evolución de empleados concretos",
            options=empleados_unicos,
            default=empleados_unicos[:5] if len(empleados_unicos) > 5 else empleados_unicos,
            key="hist_sel_semaforo",
        )
        if sel:
            df_sel = df[df["nombre"].isin(sel)].sort_values("label_sort")
            fig2 = px.line(
                df_sel, x="label", y="sin_fichar", color="nombre", markers=True,
                title="Días sin fichar por empleado (evolución)",
                labels={"label": "Mes", "sin_fichar": "Días sin fichar", "nombre": "Empleado"},
                height=360,
            )
            fig2.update_layout(plot_bgcolor="#f8f9fa",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=60, b=40))
            st.plotly_chart(fig2, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — HORAS Y HORAS EXTRA
# ═════════════════════════════════════════════════════════════════════════════
def _tab_horas(df: pd.DataFrame, mostrar_todos: bool) -> None:
    horas_mes = (
        df.groupby(["label", "label_sort"])
        .agg(horas_extra=("horas_extra", "sum"))
        .reset_index()
        .sort_values("label_sort")
    )
    horas_mes["horas_extra"] = horas_mes["horas_extra"].round(1)

    fig = go.Figure(go.Bar(
        x=horas_mes["label"],
        y=horas_mes["horas_extra"],
        marker_color=[C_VERDE if v >= 0 else C_ROJO for v in horas_mes["horas_extra"]],
        text=horas_mes["horas_extra"].astype(str) + " h",
        textposition="outside",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(
        title="Horas extra generadas por mes (verde = superávit · rojo = déficit)",
        xaxis_title="Mes", yaxis_title="Horas extra",
        height=360, margin=dict(t=60, b=40), plot_bgcolor="#f8f9fa",
    )
    st.plotly_chart(fig, use_container_width=True)

    total_extra = horas_mes["horas_extra"].sum().round(1)
    mejor = horas_mes.loc[horas_mes["horas_extra"].idxmax()]
    peor  = horas_mes.loc[horas_mes["horas_extra"].idxmin()]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total acumulado", f"{total_extra:+.1f} h")
    c2.metric("Mejor mes", f"{mejor['label']}  {mejor['horas_extra']:+.1f} h")
    c3.metric("Peor mes",  f"{peor['label']}  {peor['horas_extra']:+.1f} h")

    st.markdown("---")
    with st.expander("Desglose por empleado", expanded=False):
        meses_disp = sorted(df["label_sort"].unique())
        mes_sel = st.selectbox(
            "Selecciona mes",
            options=meses_disp,
            format_func=lambda x: df[df["label_sort"] == x]["label"].iloc[0],
            key="sel_mes_extra_emp",
        )
        df_mes = df[df["label_sort"] == mes_sel].copy()
        df_mes = df_mes.sort_values("horas_extra", ascending=False)

        fig2 = go.Figure(go.Bar(
            x=df_mes["nombre"],
            y=df_mes["horas_extra"],
            marker_color=[C_VERDE if v >= 0 else C_ROJO for v in df_mes["horas_extra"]],
            text=df_mes["horas_extra"].round(1).astype(str) + " h",
            textposition="outside",
        ))
        fig2.add_hline(y=0, line_dash="dot", line_color="gray")
        fig2.update_layout(
            title=f"Horas extra por empleado — {df_mes['label'].iloc[0] if not df_mes.empty else ''}",
            xaxis_title="Empleado", yaxis_title="Horas extra",
            height=400, margin=dict(t=60, b=120), plot_bgcolor="#f8f9fa",
            xaxis_tickangle=-35,
        )
        st.plotly_chart(fig2, use_container_width=True)

        tabla = df_mes[["nombre", "horas_reales", "objetivo", "horas_extra"]].copy()
        tabla.columns = ["Empleado", "H. Reales", "Objetivo", "H. Extra"]
        st.dataframe(tabla, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — POR RESPONSABLE (solo admin / mostrar_todos)
# ═════════════════════════════════════════════════════════════════════════════
def _tab_por_responsable(df: pd.DataFrame) -> None:
    if "responsable_id" not in df.columns:
        st.info("No hay datos de responsable en el histórico.")
        return

    meses_disp = sorted(df["label_sort"].unique())
    col_a, col_b = st.columns([2, 4])
    with col_a:
        mes_sel = st.selectbox(
            "Mes a analizar",
            options=meses_disp,
            format_func=lambda x: df[df["label_sort"] == x]["label"].iloc[0],
            key="sel_mes_resp",
            index=len(meses_disp)-1,
        )

    df_mes = df[df["label_sort"] == mes_sel].copy()
    label_mes = df_mes["label"].iloc[0] if not df_mes.empty else ""

    # Agrupación por responsable_id
    agg_resp = (
        df_mes.groupby("responsable_id")
        .agg(
            empleados=("nombre", "nunique"),
            horas_extra_total=("horas_extra", "sum"),
            horas_reales=("horas_reales", "sum"),
            objetivo=("objetivo", "sum"),
            verde=("semaforo" if "semaforo" in df_mes.columns else "sin_fichar",
                   lambda x: (x == "Verde (completo)").sum() if "semaforo" in df_mes.columns else (x == 0).sum()),
        )
        .reset_index()
    )
    agg_resp["horas_extra_total"] = agg_resp["horas_extra_total"].round(1)
    agg_resp = agg_resp.sort_values("horas_extra_total", ascending=False)

    # Gráfica horas extra por responsable
    fig1 = go.Figure(go.Bar(
        x=agg_resp["responsable_id"],
        y=agg_resp["horas_extra_total"],
        marker_color=[C_VERDE if v >= 0 else C_ROJO for v in agg_resp["horas_extra_total"]],
        text=agg_resp["horas_extra_total"].astype(str)+" h",
        textposition="outside",
    ))
    fig1.add_hline(y=0, line_dash="dot", line_color="gray")
    fig1.update_layout(
        title=f"Horas extra totales por responsable — {label_mes}",
        xaxis_title="Responsable ID", yaxis_title="Horas extra",
        height=380, margin=dict(t=60, b=80), plot_bgcolor="#f8f9fa",
        xaxis_tickangle=-25,
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Desplegable por responsable — desglose empleados
    st.markdown("---")
    st.markdown("**Desglose de horas extra por empleado y responsable**")
    responsables = sorted(df_mes["responsable_id"].unique())
    for resp_id in responsables:
        df_resp = df_mes[df_mes["responsable_id"] == resp_id].sort_values("horas_extra", ascending=False)
        total_extra = df_resp["horas_extra"].sum().round(1)
        color_extra = "🟢" if total_extra >= 0 else "🔴"
        with st.expander(
            f"{color_extra} Responsable: {resp_id}  —  {len(df_resp)} empleados  —  {total_extra:+.1f} h extra",
            expanded=False,
        ):
            fig2 = go.Figure(go.Bar(
                x=df_resp["nombre"],
                y=df_resp["horas_extra"],
                marker_color=[C_VERDE if v >= 0 else C_ROJO for v in df_resp["horas_extra"]],
                text=df_resp["horas_extra"].round(1).astype(str)+" h",
                textposition="outside",
            ))
            fig2.add_hline(y=0, line_dash="dot", line_color="gray")
            fig2.update_layout(
                height=300, margin=dict(t=30, b=100),
                plot_bgcolor="#f8f9fa", xaxis_tickangle=-30,
                yaxis_title="Horas extra",
            )
            st.plotly_chart(fig2, use_container_width=True)

            tabla = df_resp[["nombre", "horas_reales", "objetivo", "horas_extra", "sin_fichar", "errores"]].copy()
            tabla.columns = ["Empleado", "H. Reales", "Objetivo", "H. Extra", "Sin fichar", "Errores"]
            st.dataframe(tabla, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# ARCHIVOS EXCEL
# ═════════════════════════════════════════════════════════════════════════════
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
                    st.error("No se pudo guardar. Verifica que el bucket 'fichajes' existe en Supabase Storage.")
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
                    label="Descargar", data=datos, file_name=nombre,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"dl_{responsable_id}_{nombre}",
                )
        with c3:
            if st.button("🗑", key=f"del_{responsable_id}_{nombre}", help="Borrar archivo"):
                ok = _hist_repo.borrar_excel(responsable_id, nombre)
                if ok:
                    st.success("Archivo borrado.")
                    st.rerun()
