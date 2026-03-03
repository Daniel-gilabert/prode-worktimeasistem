import os
import streamlit as st
from models.empleado import Empleado
from repositories.departamento_repo import DepartamentoRepository

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_SEM_VERDE   = "#28a745"
_SEM_NARANJA = "#fd7e14"
_SEM_ROJO    = "#dc3545"
_SEM_GRIS    = "#6c757d"
_AZUL_CORP   = "#1a3d6e"


def _estado_empleado(d: dict) -> tuple[str, str]:
    sf = d["sin_fichar"]
    if sf == 0:
        return "verde", "Completo"
    if sf <= 2:
        return "naranja", f"{sf} día{'s' if sf > 1 else ''} sin fichar"
    return "rojo", f"{sf} días sin fichar"


def _color_estado(estado: str) -> str:
    return {"verde": _SEM_VERDE, "naranja": _SEM_NARANJA, "rojo": _SEM_ROJO}.get(
        estado, _SEM_GRIS
    )


def _pct(parte: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round(parte / total * 100)}%"


def _indicador_html(valor: str, etiqueta: str, color: str, subtexto: str = "") -> str:
    return f"""
    <div style="
        background:{color};border-radius:12px;padding:16px 10px 12px;
        text-align:center;color:#fff;min-width:90px;
    ">
        <div style="font-size:2rem;font-weight:700;line-height:1">{valor}</div>
        <div style="font-size:0.75rem;font-weight:600;margin-top:4px;opacity:.9">{etiqueta}</div>
        {f'<div style="font-size:0.7rem;opacity:.75;margin-top:2px">{subtexto}</div>' if subtexto else ''}
    </div>
    """


def _tarjeta_grupo(nombre_resp: str, resumenes_grupo: list[dict]) -> None:
    total    = len(resumenes_grupo)
    verdes   = sum(1 for d in resumenes_grupo if d["sin_fichar"] == 0)
    naranjas = sum(1 for d in resumenes_grupo if 0 < d["sin_fichar"] <= 2)
    rojos    = sum(1 for d in resumenes_grupo if d["sin_fichar"] > 2)
    con_err  = sum(1 for d in resumenes_grupo if d["errores"] > 0)
    cumpl    = round(verdes / total * 100) if total else 0

    color_borde = _SEM_VERDE if cumpl >= 80 else _SEM_NARANJA if cumpl >= 50 else _SEM_ROJO

    st.markdown(
        f"""<div style="
            border-left:5px solid {color_borde};background:#f8f9fa;
            border-radius:0 10px 10px 0;padding:14px 18px 10px;margin-bottom:6px;
        ">
            <span style="font-size:1rem;font-weight:700;color:{_AZUL_CORP}">{nombre_resp}</span>
            <span style="font-size:0.8rem;color:#6c757d;margin-left:10px">
                {total} empleado{'s' if total != 1 else ''}
            </span>
        </div>""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 3])
    with c1:
        st.markdown(_indicador_html(_pct(verdes, total), "Fichaje OK", _SEM_VERDE, f"{verdes} pers."), unsafe_allow_html=True)
    with c2:
        st.markdown(_indicador_html(_pct(naranjas, total), "1-2 días", _SEM_NARANJA, f"{naranjas} pers."), unsafe_allow_html=True)
    with c3:
        st.markdown(_indicador_html(_pct(rojos, total), "≥3 días", _SEM_ROJO, f"{rojos} pers."), unsafe_allow_html=True)
    with c4:
        st.markdown(_indicador_html(str(con_err), "Con errores", _SEM_ROJO if con_err else _SEM_GRIS, "fichajes"), unsafe_allow_html=True)
    with c5:
        with st.expander(f"Ver detalle — {nombre_resp}", expanded=False):
            for d in sorted(resumenes_grupo, key=lambda x: x["sin_fichar"], reverse=True):
                estado, etiqueta = _estado_empleado(d)
                color = _color_estado(estado)
                dif_str = f"+{d['diferencia']}" if d["diferencia"] > 0 else str(d["diferencia"])
                st.markdown(
                    f"""<div style="display:flex;align-items:center;gap:10px;
                        padding:6px 0;border-bottom:1px solid #eee;font-size:13px;">
                        <span style="width:11px;height:11px;border-radius:50%;
                            background:{color};flex-shrink:0;display:inline-block;"></span>
                        <span style="flex:1;font-weight:500">{d['nombre']}</span>
                        <span style="color:#555">{etiqueta}</span>
                        <span style="color:#888;font-size:12px">
                            {d['horas_reales']}h / {d['objetivo']}h &nbsp;·&nbsp; {dif_str}h
                        </span>
                    </div>""",
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='margin-bottom:14px'></div>", unsafe_allow_html=True)


def render_panel_responsables(
    usuario: Empleado,
    todos_empleados: list[Empleado],
    resumen_global: list[dict],
    mes: int,
    anno: int,
) -> None:
    nombre_mes = MESES_ES.get(mes, str(mes))
    dept_map   = DepartamentoRepository().get_todos()

    def _etiqueta_dept(resp_emp: Empleado | None, fallback: str) -> str:
        if resp_emp and dept_map.get(resp_emp.id):
            return dept_map[resp_emp.id]
        return fallback

    st.divider()

    # ── Toggle vista ──────────────────────────────────────────────────────────
    col_titulo, col_toggle = st.columns([3, 2])
    with col_titulo:
        st.subheader(f"Panel por responsable — {nombre_mes} {anno}")

    with col_toggle:
        st.markdown("<div style='padding-top:8px'></div>", unsafe_allow_html=True)
        vista = st.radio(
            "Vista",
            options=["Mi grupo", "Todos los grupos"],
            horizontal=True,
            key="panel_vista",
            label_visibility="collapsed",
        )

    if not resumen_global:
        st.info("Sin datos de resumen. Sube el Excel primero.")
        return

    resumen_por_id = {d["id"]: d for d in resumen_global}
    directorio     = {e.id: e for e in todos_empleados}

    # ── Vista: Todos los grupos ───────────────────────────────────────────────
    if vista == "Todos los grupos":
        total_g   = len(resumen_global)
        verdes_g  = sum(1 for d in resumen_global if d["sin_fichar"] == 0)
        naranjas_g= sum(1 for d in resumen_global if 0 < d["sin_fichar"] <= 2)
        rojos_g   = sum(1 for d in resumen_global if d["sin_fichar"] > 2)

        # Métricas globales
        st.markdown("#### Resumen global")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total empleados",      total_g)
        m2.metric("Fichaje completo",     f"{verdes_g} ({_pct(verdes_g, total_g)})")
        m3.metric("1-2 días sin fichar",  f"{naranjas_g} ({_pct(naranjas_g, total_g)})")
        m4.metric("≥3 días sin fichar",   f"{rojos_g} ({_pct(rojos_g, total_g)})")

        st.markdown("---")

        # Tarjetas por responsable
        responsables_ids = sorted(
            {e.responsable_id for e in todos_empleados if e.responsable_id},
            key=lambda rid: directorio.get(rid, Empleado(rid, rid, "", False, False, False)).apellidos_y_nombre,
        )
        for resp_id in responsables_ids:
            resp_emp     = directorio.get(resp_id)
            nombre_resp  = resp_emp.apellidos_y_nombre if resp_emp else f"Responsable {resp_id[:8]}"
            etiqueta     = _etiqueta_dept(resp_emp, nombre_resp)
            empleados_gr = [e for e in todos_empleados if e.responsable_id == resp_id]
            resumenes_gr = [resumen_por_id[e.id] for e in empleados_gr if e.id in resumen_por_id]
            if not resumenes_gr:
                continue
            _tarjeta_grupo(etiqueta, resumenes_gr)

        # Sin responsable
        sin_resp = [
            d for d in resumen_global
            if not any(e.responsable_id for e in todos_empleados if e.id == d["id"])
        ]
        if sin_resp:
            _tarjeta_grupo("Sin responsable asignado", sin_resp)

    # ── Vista: Mi grupo ───────────────────────────────────────────────────────
    else:
        empleados_propios = [e for e in todos_empleados if e.responsable_id == usuario.id]
        resumenes_propios = [resumen_por_id[e.id] for e in empleados_propios if e.id in resumen_por_id]

        if not resumenes_propios:
            st.info("No hay datos para tu grupo en el periodo cargado.")
            return

        _tarjeta_grupo(usuario.apellidos_y_nombre, resumenes_propios)
