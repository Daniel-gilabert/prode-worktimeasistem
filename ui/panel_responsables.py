import streamlit as st
from models.empleado import Empleado
from repositories.departamento_repo import DepartamentoRepository

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_SEM_VERDE   = "#28a745"
_SEM_AZUL    = "#17a2b8"
_SEM_NARANJA = "#fd7e14"
_SEM_ROJO    = "#dc3545"
_SEM_GRIS    = "#6c757d"
_AZUL_CORP   = "#1a3d6e"


def _estado_empleado(d: dict) -> tuple[str, str]:
    sf  = d.get("sin_fichar", 0)
    err = d.get("errores", 0)
    if sf == 0 and err == 0:
        return "verde", "Completo"
    if sf == 0 and err > 0:
        return "azul", f"{err} error{'es' if err > 1 else ''}"
    if sf <= 2:
        return "naranja", f"{sf} día{'s' if sf > 1 else ''} sin fichar"
    return "rojo", f"{sf} días sin fichar"


def _color_estado(estado: str) -> str:
    return {
        "verde": _SEM_VERDE, "azul": _SEM_AZUL,
        "naranja": _SEM_NARANJA, "rojo": _SEM_ROJO,
    }.get(estado, _SEM_GRIS)


def _pct(parte: int, total: int) -> str:
    return "0%" if total == 0 else f"{round(parte / total * 100)}%"


def _indicador_html(valor: str, etiqueta: str, color: str, subtexto: str = "") -> str:
    sub = f'<div style="font-size:0.7rem;opacity:.75;margin-top:2px">{subtexto}</div>' if subtexto else ""
    return (
        f'<div style="background:{color};border-radius:12px;padding:16px 10px 12px;'
        f'text-align:center;color:#fff;min-width:90px;">'
        f'<div style="font-size:2rem;font-weight:700;line-height:1">{valor}</div>'
        f'<div style="font-size:0.75rem;font-weight:600;margin-top:4px;opacity:.9">{etiqueta}</div>'
        f'{sub}</div>'
    )


def _descendientes_ids(raiz_id: str, todos: list[Empleado]) -> set[str]:
    """IDs de todos los empleados por debajo de raiz_id en la jerarquía (recursivo)."""
    hijos: dict[str, list[str]] = {}
    for e in todos:
        if e.responsable_id:
            hijos.setdefault(e.responsable_id, []).append(e.id)
    resultado: set[str] = set()
    cola = list(hijos.get(raiz_id, []))
    while cola:
        eid = cola.pop()
        if eid not in resultado:
            resultado.add(eid)
            cola.extend(hijos.get(eid, []))
    return resultado


def _tarjeta_grupo(etiqueta: str, resumenes_grupo: list[dict]) -> None:
    total    = len(resumenes_grupo)
    verdes   = sum(1 for d in resumenes_grupo if d.get("sin_fichar", 0) == 0 and d.get("errores", 0) == 0)
    azules   = sum(1 for d in resumenes_grupo if d.get("sin_fichar", 0) == 0 and d.get("errores", 0) > 0)
    naranjas = sum(1 for d in resumenes_grupo if 0 < d.get("sin_fichar", 0) <= 2)
    rojos    = sum(1 for d in resumenes_grupo if d.get("sin_fichar", 0) > 2)
    cumpl    = round(verdes / total * 100) if total else 0

    color_borde = _SEM_VERDE if cumpl >= 80 else _SEM_NARANJA if cumpl >= 50 else _SEM_ROJO

    st.markdown(
        f'<div style="border-left:5px solid {color_borde};background:#f8f9fa;'
        f'border-radius:0 10px 10px 0;padding:14px 18px 10px;margin-bottom:6px;">'
        f'<span style="font-size:1rem;font-weight:700;color:{_AZUL_CORP}">{etiqueta}</span>'
        f'<span style="font-size:0.8rem;color:#6c757d;margin-left:10px">'
        f'{total} empleado{"s" if total != 1 else ""}</span></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 3])
    c1.markdown(_indicador_html(_pct(verdes,   total), "Fichaje OK",   _SEM_VERDE,   f"{verdes} pers."),   unsafe_allow_html=True)
    c2.markdown(_indicador_html(_pct(azules,   total), "Con errores",  _SEM_AZUL,    f"{azules} pers."),   unsafe_allow_html=True)
    c3.markdown(_indicador_html(_pct(naranjas, total), "1-2 días",     _SEM_NARANJA, f"{naranjas} pers."), unsafe_allow_html=True)
    c4.markdown(_indicador_html(_pct(rojos,    total), "≥3 días",      _SEM_ROJO,    f"{rojos} pers."),    unsafe_allow_html=True)

    with c5:
        with st.expander(f"Ver detalle — {etiqueta}", expanded=False):
            for d in sorted(resumenes_grupo, key=lambda x: x.get("sin_fichar", 0), reverse=True):
                estado, etiq_emp = _estado_empleado(d)
                color   = _color_estado(estado)
                dif_val = d.get("diferencia", 0)
                dif_str = f"+{dif_val}" if dif_val > 0 else str(dif_val)
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;'
                    f'padding:6px 0;border-bottom:1px solid #eee;font-size:13px;">'
                    f'<span style="width:11px;height:11px;border-radius:50%;background:{color};'
                    f'flex-shrink:0;display:inline-block;"></span>'
                    f'<span style="flex:1;font-weight:500">{d["nombre"]}</span>'
                    f'<span style="color:#555">{etiq_emp}</span>'
                    f'<span style="color:#888;font-size:12px">'
                    f'{d.get("horas_reales",0)}h / {d.get("objetivo",0)}h &nbsp;&middot;&nbsp; {dif_str}h'
                    f'</span></div>',
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
    nombre_mes     = MESES_ES.get(mes, str(mes))
    dept_map       = DepartamentoRepository().get_todos()
    resumen_por_id = {d["id"]: d for d in resumen_global}
    directorio     = {e.id: e for e in todos_empleados}

    # Responsables de nivel raíz (aquellos cuyo responsable_id no está en el directorio
    # o no tiene responsable_id — los "dueños de departamento")
    ids_jefes = {e.id for e in todos_empleados if e.es_responsable or e.es_admin}

    def _etiqueta(resp_id: str) -> str:
        dept = dept_map.get(resp_id, "")
        if dept:
            return dept
        emp = directorio.get(resp_id)
        return emp.apellidos_y_nombre if emp else resp_id[:12]

    def _resumenes_dept(resp_id: str) -> list[dict]:
        """Todos los resumenes de empleados bajo resp_id (recursivo)."""
        ids = _descendientes_ids(resp_id, todos_empleados)
        return [resumen_por_id[eid] for eid in ids if eid in resumen_por_id]

    st.divider()

    col_titulo, col_toggle = st.columns([3, 2])
    with col_titulo:
        st.subheader(f"Panel por departamento — {nombre_mes} {anno}")
    with col_toggle:
        st.markdown("<div style='padding-top:8px'></div>", unsafe_allow_html=True)
        vista = st.radio(
            "Vista", options=["Mi departamento", "Todos los departamentos"],
            horizontal=True, key="panel_vista", label_visibility="collapsed",
        )

    if not resumen_global:
        st.info("Sin datos de resumen. Sube el Excel primero.")
        return

    # ── Vista: Todos los departamentos ────────────────────────────────────────
    if vista == "Todos los departamentos":
        total_g    = len(resumen_global)
        verdes_g   = sum(1 for d in resumen_global if d.get("sin_fichar",0)==0 and d.get("errores",0)==0)
        azules_g   = sum(1 for d in resumen_global if d.get("sin_fichar",0)==0 and d.get("errores",0)>0)
        naranjas_g = sum(1 for d in resumen_global if 0 < d.get("sin_fichar",0) <= 2)
        rojos_g    = sum(1 for d in resumen_global if d.get("sin_fichar",0) > 2)

        st.markdown("#### Resumen global")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total empleados",     total_g)
        m2.metric("🟢 Fichaje completo", f"{verdes_g} ({_pct(verdes_g, total_g)})")
        m3.metric("🔵 Con errores",      f"{azules_g} ({_pct(azules_g, total_g)})")
        m4.metric("🟠 1-2 días",         f"{naranjas_g} ({_pct(naranjas_g, total_g)})")
        m5.metric("🔴 ≥3 días",          f"{rojos_g} ({_pct(rojos_g, total_g)})")
        st.markdown("---")

        # Responsables raíz de cada departamento (los que tienen dept asignado
        # o son responsables sin padre responsable)
        raices_resp = [
            e for e in todos_empleados
            if (e.es_responsable or e.es_admin)
            and (not e.responsable_id or e.responsable_id not in ids_jefes)
        ]
        raices_resp = sorted(raices_resp, key=lambda e: (_etiqueta(e.id)))

        for resp in raices_resp:
            resumenes = _resumenes_dept(resp.id)
            if not resumenes:
                continue
            _tarjeta_grupo(_etiqueta(resp.id), resumenes)

        # Sin responsable
        ids_con_resp = {eid for eid in resumen_por_id if directorio.get(eid) and directorio[eid].responsable_id}
        sin_resp = [d for d in resumen_global if d["id"] not in ids_con_resp]
        if sin_resp:
            _tarjeta_grupo("Sin departamento asignado", sin_resp)

    # ── Vista: Mi departamento ─────────────────────────────────────────────────
    else:
        resumenes = _resumenes_dept(usuario.id)
        if not resumenes:
            st.info("No hay datos para tu grupo en el periodo cargado.")
            return
        etiq = _etiqueta(usuario.id)
        _tarjeta_grupo(etiq, resumenes)
