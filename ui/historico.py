import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from models.empleado import Empleado
from repositories.historico_repo import HistoricoRepository
from repositories.departamento_repo import DepartamentoRepository

MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

_hist_repo = HistoricoRepository()
_dept_repo = DepartamentoRepository()

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
    todos_empleados: list | None = None,
) -> None:
    todos_empleados = todos_empleados or []
    dept_map = _dept_repo.get_todos()
    mapa_resp = {e.id: e.apellidos_y_nombre for e in todos_empleados if e.es_responsable or e.es_admin}
    ids_responsable = {e.id for e in todos_empleados if e.es_responsable or e.es_admin}

    def _etiqueta(rid: str) -> str:
        d = dept_map.get(rid, "")
        return d if d else mapa_resp.get(rid, rid[:12] if rid else "Sin asignar")

    st.divider()
    st.markdown('<a name="historico-evolucion"></a>', unsafe_allow_html=True)
    st.subheader("Histórico y evolución")

    responsable_id = "global" if mostrar_todos else usuario.id

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

    with st.expander("Archivos Excel guardados", expanded=False):
        _render_archivos(usuario, responsable_id, anno, mes, resumen_actual)

    historico = _hist_repo.get_historico(responsable_id)
    if not historico:
        st.info("Guarda al menos un periodo para ver las gráficas de evolución.")
        return

    df = pd.DataFrame(historico)
    df["label"]       = df.apply(lambda r: _label_mes(int(r["anno"]), int(r["mes"])), axis=1)
    df["label_sort"]  = df["anno"].astype(str) + df["mes"].astype(str).str.zfill(2)
    df["horas_extra"] = pd.to_numeric(df.get("horas_extra", 0), errors="coerce").fillna(0)
    df["semaforo"]    = df.apply(_clasificar_semaforo, axis=1)
    df = df.sort_values("label_sort")

    tabs = ["📊 Evolución fichaje", "⏱ Horas extra"]
    if mostrar_todos:
        tabs.append("👥 Por responsable")

    tab_list = st.tabs(tabs)

    with tab_list[0]:
        _tab_semaforo(df, mostrar_todos, _etiqueta)

    with tab_list[1]:
        _tab_horas(df, mostrar_todos, resumen_actual, ids_responsable, _etiqueta)

    if mostrar_todos and len(tab_list) > 2:
        with tab_list[2]:
            _tab_por_responsable(df, _etiqueta)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — EVOLUCIÓN FICHAJE (4 variables semáforo)
# ═════════════════════════════════════════════════════════════════════════════
def _tab_semaforo(df: pd.DataFrame, mostrar_todos: bool, etiqueta_fn) -> None:
    resumen_mes = (
        df.groupby(["label", "label_sort"])
        .agg(
            total=(    "nombre",   "count"),
            verde=(    "semaforo", lambda x: (x == "Verde (completo)").sum()),
            azul=(     "semaforo", lambda x: (x == "Azul (errores)").sum()),
            naranja=(  "semaforo", lambda x: (x == "Naranja (1-2 días)").sum()),
            rojo=(     "semaforo", lambda x: (x == "Rojo (≥3 días)").sum()),
        )
        .reset_index()
        .sort_values("label_sort")
    )
    for col in ["verde", "azul", "naranja", "rojo"]:
        resumen_mes[f"pct_{col}"] = (resumen_mes[col] / resumen_mes["total"] * 100).round(1)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_verde"],
        name="🟢 Fichaje completo", marker_color=C_VERDE,
        text=resumen_mes["pct_verde"].astype(str)+"%", textposition="inside"))
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_azul"],
        name="🔵 Con errores", marker_color=C_AZUL,
        text=resumen_mes["pct_azul"].astype(str)+"%", textposition="inside"))
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_naranja"],
        name="🟠 1-2 días sin fichar", marker_color=C_NARANJA,
        text=resumen_mes["pct_naranja"].astype(str)+"%", textposition="inside"))
    fig.add_trace(go.Bar(x=resumen_mes["label"], y=resumen_mes["pct_rojo"],
        name="🔴 ≥3 días sin fichar", marker_color=C_ROJO,
        text=resumen_mes["pct_rojo"].astype(str)+"%", textposition="inside"))
    fig.update_layout(
        barmode="stack",
        title="Distribución semáforo por mes (% empleados)",
        xaxis_title="Mes", yaxis=dict(title="%", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400, margin=dict(t=70, b=40), plot_bgcolor="#f8f9fa",
    )
    st.plotly_chart(fig, use_container_width=True)

    if not resumen_mes.empty:
        ultimo = resumen_mes.iloc[-1]
        st.caption(f"Último periodo guardado: **{ultimo['label']}** — {int(ultimo['total'])} empleados")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 Fichaje completo", f"{int(ultimo['verde'])} ({ultimo['pct_verde']}%)")
        c2.metric("🔵 Con errores",      f"{int(ultimo['azul'])} ({ultimo['pct_azul']}%)")
        c3.metric("🟠 1-2 días",         f"{int(ultimo['naranja'])} ({ultimo['pct_naranja']}%)")
        c4.metric("🔴 ≥3 días",          f"{int(ultimo['rojo'])} ({ultimo['pct_rojo']}%)")

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
            fig2 = go.Figure()
            for nombre in sel:
                d = df_sel[df_sel["nombre"] == nombre]
                fig2.add_trace(go.Scatter(
                    x=d["label"], y=d["sin_fichar"],
                    mode="lines+markers", name=nombre,
                ))
            fig2.update_layout(
                title="Días sin fichar por empleado (evolución)",
                xaxis_title="Mes", yaxis_title="Días sin fichar",
                height=360, margin=dict(t=60, b=40), plot_bgcolor="#f8f9fa",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig2, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — HORAS EXTRA
# ═════════════════════════════════════════════════════════════════════════════
def _tab_horas(
    df: pd.DataFrame,
    mostrar_todos: bool,
    resumen_actual: list[dict],
    ids_responsable: set,
    etiqueta_fn,
) -> None:

    # ── VISTA ADMINISTRADOR ───────────────────────────────────────────────────
    if mostrar_todos and resumen_actual:
        with st.expander("⚙️ Editar nombres de departamento", expanded=False):
            st.caption("Asigna el nombre del departamento a cada responsable. Se mostrará en todos los paneles y gráficas.")
            dept_map_live = _dept_repo.get_todos()
            todos_resp = [e for _, e in [(etiqueta_fn(eid), eid) for eid in ids_responsable]]
            # Usamos el df para obtener empleados únicos si no tenemos la lista completa
            for rid in sorted(ids_responsable):
                c1, c2, c3 = st.columns([3, 4, 1])
                c1.markdown(f"`{rid[:8]}…`")
                nuevo = c2.text_input(
                    "dept", value=dept_map_live.get(rid, ""),
                    key=f"dept_{rid}", label_visibility="collapsed",
                    placeholder="Ej: Casa de Acogida de Córdoba",
                )
                with c3:
                    if st.button("💾", key=f"save_dept_{rid}", help="Guardar"):
                        _dept_repo.upsert(rid, nuevo)
                        st.success("Guardado")
                        st.rerun()

        st.markdown("#### Distribución de horas extra por departamento — mes en curso")

        grupos: dict[str, list[dict]] = {}
        for emp_data in resumen_actual:
            rid = emp_data.get("responsable_id") or "sin_asignar"
            grupos.setdefault(rid, []).append(emp_data)

        totales = {
            rid: round(sum(e.get("horas_extra", 0) for e in emps), 1)
            for rid, emps in grupos.items()
        }
        total_global = round(sum(totales.values()), 1)

        etiquetas = [etiqueta_fn(rid) for rid in totales]
        valores   = list(totales.values())
        pcts      = [round(v / total_global * 100, 1) if total_global else 0.0 for v in valores]

        fig = go.Figure(go.Bar(
            x=etiquetas, y=pcts,
            marker_color=[C_VERDE if v >= 0 else C_ROJO for v in valores],
            text=[f"{p}%<br>{v:+.1f} h" for p, v in zip(pcts, valores)],
            textposition="outside",
        ))
        fig.add_hline(y=0, line_dash="dot", line_color="gray")
        fig.update_layout(
            title="% de horas extra por departamento sobre el total de la entidad",
            xaxis_title="Departamento", yaxis_title="% del total",
            height=420, margin=dict(t=60, b=130),
            plot_bgcolor="#f8f9fa", xaxis_tickangle=-30,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.metric("Total horas extra — toda la entidad este mes", f"{total_global:+.1f} h")
        st.markdown("---")

        for rid, emps in sorted(grupos.items(), key=lambda x: -abs(totales[x[0]])):
            total_extra = totales[rid]
            etiq  = etiqueta_fn(rid)
            n_emp = len(emps)
            icono = "⚪" if total_extra == 0 else ("🔴" if total_extra > 20 else ("🟠" if total_extra > 0 else "🟢"))

            with st.expander(
                f"{icono}  **{etiq}**  —  {n_emp} personas  —  {total_extra:+.1f} h extra",
                expanded=False,
            ):
                rows = []
                for e in sorted(emps, key=lambda x: -x.get("horas_extra", 0)):
                    extra = e.get("horas_extra", 0)
                    em_ic = "🟢" if extra == 0 else ("🟠" if 0 < extra <= 10 else "🔴")
                    rows.append({
                        "Estado":    em_ic,
                        "Rol":       "Responsable" if e.get("id", "") in ids_responsable else "Empleado",
                        "Nombre":    e["nombre"],
                        "H. Reales": e.get("horas_reales", 0),
                        "Objetivo":  e.get("objetivo", 0),
                        "H. Extra":  extra,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return

    # ── VISTA RESPONSABLE: histórico horas extra ──────────────────────────────
    horas_mes = (
        df.groupby(["label", "label_sort"])
        .agg(horas_extra=("horas_extra", "sum"))
        .reset_index()
        .sort_values("label_sort")
    )
    horas_mes["horas_extra"] = horas_mes["horas_extra"].round(1)

    fig = go.Figure(go.Bar(
        x=horas_mes["label"], y=horas_mes["horas_extra"],
        marker_color=[C_VERDE if v >= 0 else C_ROJO for v in horas_mes["horas_extra"]],
        text=horas_mes["horas_extra"].astype(str) + " h", textposition="outside",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(
        title="Horas extra generadas por mes (verde = superávit · rojo = déficit)",
        xaxis_title="Mes", yaxis_title="Horas extra",
        height=360, margin=dict(t=60, b=40), plot_bgcolor="#f8f9fa",
    )
    st.plotly_chart(fig, use_container_width=True)

    if not horas_mes.empty:
        t     = horas_mes["horas_extra"].sum().round(1)
        mejor = horas_mes.loc[horas_mes["horas_extra"].idxmax()]
        peor  = horas_mes.loc[horas_mes["horas_extra"].idxmin()]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total acumulado", f"{t:+.1f} h")
        c2.metric("Mejor mes", f"{mejor['label']}  {mejor['horas_extra']:+.1f} h")
        c3.metric("Peor mes",  f"{peor['label']}  {peor['horas_extra']:+.1f} h")

    st.markdown("---")
    with st.expander("Desglose por empleado", expanded=False):
        meses_disp = sorted(df["label_sort"].unique())
        if not meses_disp:
            st.info("Sin datos históricos.")
            return
        mes_sel = st.selectbox(
            "Selecciona mes", options=meses_disp,
            format_func=lambda x: df[df["label_sort"] == x]["label"].iloc[0],
            key="sel_mes_extra_emp",
        )
        df_mes = df[df["label_sort"] == mes_sel].copy().sort_values("horas_extra", ascending=False)
        fig2 = go.Figure(go.Bar(
            x=df_mes["nombre"], y=df_mes["horas_extra"],
            marker_color=[C_VERDE if v >= 0 else C_ROJO for v in df_mes["horas_extra"]],
            text=df_mes["horas_extra"].round(1).astype(str) + " h", textposition="outside",
        ))
        fig2.add_hline(y=0, line_dash="dot", line_color="gray")
        fig2.update_layout(
            title=f"Horas extra — {df_mes['label'].iloc[0] if not df_mes.empty else ''}",
            xaxis_title="Empleado", yaxis_title="Horas extra",
            height=400, margin=dict(t=60, b=120), plot_bgcolor="#f8f9fa", xaxis_tickangle=-35,
        )
        st.plotly_chart(fig2, use_container_width=True)
        tabla = df_mes[["nombre", "horas_reales", "objetivo", "horas_extra"]].copy()
        tabla.columns = ["Empleado", "H. Reales", "Objetivo", "H. Extra"]
        st.dataframe(tabla, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — POR RESPONSABLE (solo admin)
# ═════════════════════════════════════════════════════════════════════════════
def _tab_por_responsable(df: pd.DataFrame, etiqueta_fn) -> None:
    if df.empty:
        st.info("Sin datos históricos.")
        return

    meses_disp = sorted(df["label_sort"].unique())
    mes_sel = st.selectbox(
        "Mes a analizar", options=meses_disp,
        format_func=lambda x: df[df["label_sort"] == x]["label"].iloc[0],
        key="sel_mes_resp", index=len(meses_disp)-1,
    )
    df_mes = df[df["label_sort"] == mes_sel].copy()
    label_mes = df_mes["label"].iloc[0] if not df_mes.empty else ""

    if "responsable_id" not in df_mes.columns:
        st.info("No hay datos de responsable en el histórico.")
        return

    df_mes["dept"] = df_mes["responsable_id"].apply(etiqueta_fn)

    agg = (
        df_mes.groupby("dept")
        .agg(
            empleados=("nombre", "nunique"),
            horas_extra=("horas_extra", "sum"),
            sin_fichar=("sin_fichar", "sum"),
            errores=("errores", "sum"),
        )
        .reset_index()
        .sort_values("horas_extra", ascending=False)
    )
    agg["horas_extra"] = agg["horas_extra"].round(1)

    fig = go.Figure(go.Bar(
        x=agg["dept"], y=agg["horas_extra"],
        marker_color=[C_VERDE if v >= 0 else C_ROJO for v in agg["horas_extra"]],
        text=agg["horas_extra"].astype(str) + " h", textposition="outside",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(
        title=f"Horas extra totales por departamento — {label_mes}",
        xaxis_title="Departamento", yaxis_title="Horas extra",
        height=380, margin=dict(t=60, b=100), plot_bgcolor="#f8f9fa", xaxis_tickangle=-25,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    for _, fila in agg.sort_values("horas_extra", ascending=False).iterrows():
        df_resp = df_mes[df_mes["dept"] == fila["dept"]].sort_values("horas_extra", ascending=False)
        total = fila["horas_extra"]
        icono = "⚪" if total == 0 else ("🔴" if total > 20 else ("🟠" if total > 0 else "🟢"))
        with st.expander(
            f"{icono}  **{fila['dept']}**  —  {int(fila['empleados'])} empleados  —  {total:+.1f} h extra",
            expanded=False,
        ):
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
                    st.success("Excel guardado.")
                    st.rerun()
                else:
                    st.error("No se pudo guardar. Verifica que el bucket 'fichajes' existe en Supabase Storage.")
            else:
                st.warning("Sube un Excel primero.")

    if not archivos:
        st.info("No hay archivos guardados.")
        return

    st.markdown(f"**{len(archivos)} archivo(s) guardado(s)**")
    for archivo in sorted(archivos, key=lambda x: x.get("name", ""), reverse=True):
        nombre = archivo.get("name", "")
        if not nombre:
            continue
        tamaño = archivo.get("metadata", {}).get("size", 0)
        tam_str = f"{round(tamaño / 1024)} KB" if tamaño else ""
        c1, c2, c3 = st.columns([4, 2, 1])
        c1.markdown(f"📄 **{nombre}** {f'`{tam_str}`' if tam_str else ''}")
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
