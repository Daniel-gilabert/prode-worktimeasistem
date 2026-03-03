import streamlit as st
from core.auth import check_login

from datetime import date
import pandas as pd
from core.queries import get_servicios, get_empleados, get_vehiculos, calcular_estado_servicio
from core.documentos import get_documentos, subir_documento, borrar_documento, TIPOS_DOCUMENTO, get_icono_tipo
from core.db import get_supabase

st.set_page_config(page_title="Servicios", layout="wide")

check_login()
st.title("Servicios")

tab_lista, tab_ficha, tab_nuevo, tab_importar = st.tabs([
    "Lista de servicios", "Ficha completa", "Nuevo servicio", "ðŸ“¥ Importar Excel"
])

hoy = date.today()

ESTADO_BADGE = {
    "OPERATIVO":    ("ðŸŸ¢", "#DCFCE7", "#166534"),
    "EN_RIESGO":    ("ðŸŸ¡", "#FEF9C3", "#854D0E"),
    "NO_OPERATIVO": ("ðŸ”´", "#FEE2E2", "#991B1B"),
}

FORMAS_PAGO = ["Transferencia", "Confirming", "Remesa"]

TIPO_COLORES_DOC = {
    "Contrato":               ("ðŸ“œ", "#EDE9FE", "#4C1D95"),
    "Seguro vehÃ­culo":        ("ðŸ›¡ï¸", "#DCFCE7", "#166534"),
    "Permiso / AutorizaciÃ³n": ("âœ…", "#FEF9C3", "#854D0E"),
    "Factura":                ("ðŸ’¶", "#FEE2E2", "#991B1B"),
    "Parte de trabajo":       ("ðŸ“‹", "#E0F2FE", "#0C4A6E"),
    "Ficha tÃ©cnica vehÃ­culo": ("ðŸ”§", "#F3F4F6", "#374151"),
    "DocumentaciÃ³n empleado": ("ðŸ‘¤", "#FEF3C7", "#92400E"),
    "Acuerdo de servicio":    ("ðŸ¤", "#F0FDF4", "#14532D"),
    "Otro":                   ("ðŸ“Ž", "#F9FAFB", "#4B5563"),
}

def n(v): return v if v else None


def _mostrar_ficha(srv: dict):
    sid = srv["id"]

    # Estado operativo
    try:
        estado = calcular_estado_servicio(srv, hoy)
        ico, bg, fg = ESTADO_BADGE[estado.estado]
        st.markdown(
            f"<div style='background:{bg};color:{fg};padding:10px 18px;border-radius:10px;"
            f"font-weight:600;font-size:1rem;margin-bottom:12px'>"
            f"{ico} Estado hoy: {estado.estado.replace('_',' ')}"
            + (f" â€” {' | '.join(m.descripcion for m in estado.motivos)}" if estado.motivos else "")
            + "</div>", unsafe_allow_html=True
        )
    except Exception as e:
        st.warning(f"No se pudo calcular estado: {e}")

    # Formulario de ediciÃ³n
    with st.expander("âœï¸ Editar datos del servicio", expanded=False):
        empleados = get_empleados()
        vehiculos = get_vehiculos()
        opts_emp  = {f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados}
        opts_veh  = {f"{v['matricula']} â€” {v['marca']} {v['modelo']}": v["id"] for v in vehiculos}
        idx_emp   = list(opts_emp.values()).index(srv["empleado_base_id"]) if srv["empleado_base_id"] in opts_emp.values() else 0
        idx_veh   = list(opts_veh.values()).index(srv["vehiculo_base_id"]) if srv["vehiculo_base_id"] in opts_veh.values() else 0

        with st.form(f"form_editar_srv_{sid}"):
            st.subheader("Datos bÃ¡sicos")
            c1, c2, c3, c4 = st.columns(4)
            codigo      = c1.text_input("CÃ³digo",      value=srv.get("codigo",""),           key=f"cod_{sid}")
            descripcion = c2.text_input("DescripciÃ³n", value=srv.get("descripcion",""),       key=f"desc_{sid}")
            zona        = c3.text_input("Zona",        value=srv.get("zona","") or "",        key=f"zona_{sid}")
            dimension   = c4.text_input("DimensiÃ³n",   value=srv.get("dimension","") or "",  key=f"dim_{sid}")

            c1, c2 = st.columns(2)
            fi_str  = srv.get("fecha_inicio_contrato","")
            ff_str  = srv.get("fecha_fin_contrato","")
            fi_val  = date.fromisoformat(str(fi_str)[:10]) if fi_str else hoy
            ff_val  = date.fromisoformat(str(ff_str)[:10]) if ff_str else None
            fi_cont = c1.date_input("Fecha inicio del servicio", value=fi_val, key=f"fi_{sid}")
            tiene_fin = c2.checkbox("Â¿Tiene fecha de fin?", value=ff_val is not None, key=f"tfin_{sid}")
            ff_cont = None
            if tiene_fin:
                ff_cont = c2.date_input("Fecha fin del servicio", value=ff_val or hoy, key=f"ff_{sid}")

            st.subheader("Recursos asignados")
            c1, c2 = st.columns(2)
            emp_sel = c1.selectbox("Empleado base", list(opts_emp.keys()), index=idx_emp, key=f"emp_{sid}")
            veh_sel = c2.selectbox("VehÃ­culo base", list(opts_veh.keys()), index=idx_veh, key=f"veh_{sid}")

            st.subheader("Datos empresa cliente")
            c1, c2, c3 = st.columns(3)
            emp_nombre = c1.text_input("RazÃ³n social",    value=srv.get("empresa_nombre","") or "",           key=f"enombre_{sid}")
            emp_cif    = c2.text_input("CIF / NIF",       value=srv.get("empresa_cif","") or "",              key=f"ecif_{sid}")
            emp_pais   = c3.text_input("PaÃ­s",            value=srv.get("empresa_pais","EspaÃ±a") or "EspaÃ±a", key=f"epais_{sid}")
            emp_dir    = st.text_input("DirecciÃ³n fiscal", value=srv.get("empresa_direccion","") or "",        key=f"edir_{sid}")
            c1, c2, c3 = st.columns(3)
            emp_cp     = c1.text_input("CÃ³digo postal",   value=srv.get("empresa_cp","") or "",               key=f"ecp_{sid}")
            emp_ciudad = c2.text_input("Ciudad",          value=srv.get("empresa_ciudad","") or "",           key=f"eciu_{sid}")
            emp_prov   = c3.text_input("Provincia",       value=srv.get("empresa_provincia","") or "",        key=f"eprov_{sid}")

            st.subheader("Contacto principal")
            c1, c2 = st.columns(2)
            ct_nombre = c1.text_input("Nombre contacto",    value=srv.get("contacto_nombre","") or "",    key=f"ctnombre_{sid}")
            ct_cargo  = c2.text_input("Cargo",              value=srv.get("contacto_cargo","") or "",     key=f"ctcargo_{sid}")
            c1, c2, c3 = st.columns(3)
            ct_email  = c1.text_input("Email principal",    value=srv.get("contacto_email","") or "",     key=f"ctemail_{sid}")
            ct_tel    = c2.text_input("TelÃ©fono principal", value=srv.get("contacto_telefono","") or "",  key=f"cttel_{sid}")
            ct_movil  = c3.text_input("MÃ³vil",              value=srv.get("contacto_movil","") or "",     key=f"ctmovil_{sid}")

            st.subheader("Contacto secundario")
            c1, c2, c3 = st.columns(3)
            ct2_nombre = c1.text_input("Nombre secundario",    value=srv.get("contacto2_nombre","") or "",   key=f"ct2nombre_{sid}")
            ct2_email  = c2.text_input("Email secundario",     value=srv.get("contacto2_email","") or "",    key=f"ct2email_{sid}")
            ct2_tel    = c3.text_input("TelÃ©fono secundario",  value=srv.get("contacto2_telefono","") or "", key=f"ct2tel_{sid}")

            st.subheader("FacturaciÃ³n")
            c1, c2, c3 = st.columns(3)
            fac_email  = c1.text_input("Email facturación", value=srv.get("facturacion_email","") or "", key=f"facemail_{sid}")
            fp_actual  = srv.get("facturacion_forma_pago","") or ""
            fp_idx     = FORMAS_PAGO.index(fp_actual) if fp_actual in FORMAS_PAGO else 0
            fac_pago   = c2.selectbox("Forma de pago", FORMAS_PAGO, index=fp_idx, key=f"facpago_{sid}")

            obs = st.text_area("Observaciones", value=srv.get("observaciones","") or "", key=f"obs_{sid}")

            if st.form_submit_button("ðŸ’¾ Guardar cambios", type="primary"):
                try:
                    get_supabase().table("servicios").update({
                        "codigo": codigo, "descripcion": descripcion, "zona": n(zona),
                        "dimension": n(dimension),
                        "fecha_inicio_contrato": str(fi_cont),
                        "fecha_fin_contrato": str(ff_cont) if ff_cont else None,
                        "empleado_base_id": opts_emp[emp_sel],
                        "vehiculo_base_id": opts_veh[veh_sel],
                        "empresa_nombre": n(emp_nombre), "empresa_cif": n(emp_cif),
                        "empresa_direccion": n(emp_dir), "empresa_cp": n(emp_cp),
                        "empresa_ciudad": n(emp_ciudad), "empresa_provincia": n(emp_prov),
                        "empresa_pais": emp_pais or "EspaÃ±a",
                        "contacto_nombre": n(ct_nombre), "contacto_cargo": n(ct_cargo),
                        "contacto_email": n(ct_email), "contacto_telefono": n(ct_tel),
                        "contacto_movil": n(ct_movil),
                        "contacto2_nombre": n(ct2_nombre), "contacto2_email": n(ct2_email),
                        "contacto2_telefono": n(ct2_tel),
                        "facturacion_email": n(fac_email), "facturacion_forma_pago": n(fac_pago),
                        "observaciones": n(obs),
                    }).eq("id", sid).execute()
                    st.success("Servicio actualizado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # Vista de datos actuales
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### ðŸ¢ Empresa cliente")
        st.write(f"**{srv.get('empresa_nombre') or 'â€”'}**")
        st.write(f"CIF: `{srv.get('empresa_cif') or 'â€”'}`")
        st.write(f"{srv.get('empresa_direccion') or 'â€”'}")
        st.write(f"{srv.get('empresa_cp') or ''} {srv.get('empresa_ciudad') or ''} ({srv.get('empresa_provincia') or 'â€”'})")
        st.write(f"{srv.get('empresa_pais') or 'â€”'}")
    with c2:
        st.markdown("#### ðŸ“ž Contactos")
        st.write(f"**{srv.get('contacto_nombre') or 'â€”'}**")
        st.write(f"{srv.get('contacto_cargo') or 'â€”'}")
        if srv.get("contacto_email"):   st.write(f"âœ‰ï¸ {srv['contacto_email']}")
        if srv.get("contacto_telefono"): st.write(f"ðŸ“ž {srv['contacto_telefono']}")
        if srv.get("contacto_movil"):   st.write(f"ðŸ“± {srv['contacto_movil']}")
        if srv.get("contacto2_nombre"):
            st.markdown("**Contacto secundario:**")
            st.write(f"{srv['contacto2_nombre']}")
            if srv.get("contacto2_email"):    st.write(f"âœ‰ï¸ {srv['contacto2_email']}")
            if srv.get("contacto2_telefono"): st.write(f"ðŸ“ž {srv['contacto2_telefono']}")
    with c3:
        st.markdown("#### ðŸ“‹ Datos del servicio")
        st.write(f"Inicio: {srv.get('fecha_inicio_contrato') or 'â€”'}")
        if srv.get("fecha_fin_contrato"):
            st.write(f"Fin: {srv['fecha_fin_contrato']}")
        else:
            st.markdown("<span style='background:#DCFCE7;color:#166534;padding:2px 10px;"
                        "border-radius:6px;font-size:.85rem;font-weight:600'>âœ… ACTIVO â€” sin fecha de fin</span>",
                        unsafe_allow_html=True)
        if srv.get("dimension"):              st.write(f"DimensiÃ³n: **{srv['dimension']}**")
        if srv.get("facturacion_email"):      st.write(f"FacturaciÃ³n: {srv['facturacion_email']}")
        if srv.get("facturacion_forma_pago"): st.write(f"Pago: **{srv['facturacion_forma_pago']}**")
        if srv.get("observaciones"):          st.caption(f"ðŸ“Œ {srv['observaciones']}")

    # Repositorio de documentos
    st.divider()
    st.markdown("#### ðŸ“ Documentos del servicio")
    try:
        docs = get_documentos(sid)
        tabla_docs_ok = True
    except Exception:
        docs = []
        tabla_docs_ok = False

    if not tabla_docs_ok:
        st.warning("La tabla de documentos no existe. Ejecuta el SQL de esquema en Supabase.")
    else:
        with st.expander("âž• Subir nuevo documento", expanded=len(docs) == 0):
            with st.form(f"form_doc_{sid}"):
                c1, c2 = st.columns(2)
                doc_nombre = c1.text_input("Nombre del documento *", key=f"dnombre_{sid}")
                doc_tipo   = c2.selectbox("Tipo *", TIPOS_DOCUMENTO, key=f"dtipo_{sid}")
                doc_desc   = st.text_input("DescripciÃ³n (opcional)", key=f"ddesc_{sid}")
                archivo    = st.file_uploader(
                    "Archivo (PDF, Word, Excel, imagen...)",
                    type=["pdf","doc","docx","xls","xlsx","jpg","jpeg","png","txt","zip"],
                    key=f"dfile_{sid}"
                )
                if st.form_submit_button("ðŸ“¤ Subir documento", type="primary"):
                    if not doc_nombre:
                        st.error("El nombre es obligatorio.")
                    elif not archivo:
                        st.error("Selecciona un archivo.")
                    else:
                        with st.spinner("Subiendo..."):
                            try:
                                subir_documento(
                                    servicio_id=sid, nombre=doc_nombre, tipo=doc_tipo,
                                    archivo_bytes=archivo.read(), nombre_archivo=archivo.name,
                                    descripcion=doc_desc or None,
                                )
                                st.success(f"Documento **{doc_nombre}** subido.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al subir: {e}")

        if not docs:
            st.info("No hay documentos todavÃ­a.")
        else:
            st.write(f"**{len(docs)} documento(s)**")
            for doc in docs:
                ico_tipo, bg, fg = TIPO_COLORES_DOC.get(doc["tipo"], ("ðŸ“Ž", "#F9FAFB", "#4B5563"))
                ico_arch = get_icono_tipo(doc["nombre_archivo"])
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([0.4, 2.5, 1.5, 2, 1.2])
                    c1.markdown(f"<div style='font-size:1.4rem;text-align:center'>{ico_arch}</div>",
                                unsafe_allow_html=True)
                    with c2:
                        st.write(f"**{doc['nombre']}**")
                        if doc.get("descripcion"): st.caption(doc["descripcion"])
                    c3.markdown(f"<span style='background:{bg};color:{fg};padding:2px 8px;"
                                f"border-radius:6px;font-size:.75rem'>{ico_tipo} {doc['tipo']}</span>",
                                unsafe_allow_html=True)
                    c4.caption(f"Subido: {str(doc['fecha_subida'])[:10]}")
                    with c5:
                        if doc.get("url_publica"):
                            st.link_button("â¬‡ï¸ Descargar", doc["url_publica"])
                        if st.button("ðŸ—‘ï¸", key=f"del_doc_{doc['id']}_{sid}", help="Eliminar"):
                            borrar_documento(doc["id"], doc["storage_path"])
                            st.success("Documento eliminado.")
                            st.rerun()


# â”€â”€ Lista de servicios â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_lista:
    fecha     = st.date_input("Ver estado para:", value=hoy, key="fecha_lista")
    servicios = get_servicios()

    if not servicios:
        st.info("No hay servicios registrados. CrÃ©alos en la pestaÃ±a 'Nuevo servicio'.")
    else:
        sel_id = st.session_state.get("servicio_seleccionado")
        for s in servicios:
            try:
                estado = calcular_estado_servicio(s, fecha)
                ico, bg, fg = ESTADO_BADGE[estado.estado]
            except Exception:
                ico, bg, fg, estado = "âšª", "#F3F4F6", "#374151", None

            abierto = sel_id == s["id"]
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2.5, 2, 2, 1.5, 1.5])
                with c1:
                    st.markdown(f"**`{s['codigo']}`**")
                    if s.get("zona"): st.caption(s["zona"])
                with c2:
                    st.write(s["descripcion"])
                    if s.get("empresa_nombre"): st.caption(f"ðŸ¢ {s['empresa_nombre']}")
                with c3:
                    st.write(f"ðŸ‘¤ {s['empleado_base_nombre']}")
                with c4:
                    st.write(f"ðŸš `{s['vehiculo_base_matricula']}`")
                with c5:
                    st.markdown(
                        f"<span style='background:{bg};color:{fg};padding:3px 10px;"
                        f"border-radius:99px;font-size:.8rem;font-weight:600'>"
                        f"{ico} {estado.estado.replace('_',' ') if estado else 'â€”'}</span>",
                        unsafe_allow_html=True
                    )
                with c6:
                    label = "â–² Cerrar" if abierto else "ðŸ“‹ Ver ficha"
                    if st.button(label, key=f"btn_ficha_{s['id']}"):
                        if abierto:
                            st.session_state.pop("servicio_seleccionado", None)
                        else:
                            st.session_state["servicio_seleccionado"] = s["id"]
                        st.rerun()

                if abierto:
                    st.divider()
                    _mostrar_ficha(s)

# â”€â”€ Ficha completa del servicio â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_ficha:
    servicios = get_servicios()
    if not servicios:
        st.info("No hay servicios creados todavÃ­a.")
    else:
        opts    = {f"{s['codigo']} â€” {s['descripcion']}": s for s in servicios}
        sel_key = st.session_state.get("servicio_seleccionado")
        default = next((i for i, s in enumerate(servicios) if s["id"] == sel_key), 0)
        sel     = st.selectbox("Selecciona servicio", list(opts.keys()), index=default, key="sel_ficha")
        srv     = opts[sel]
        _mostrar_ficha(srv)

# â”€â”€ Nuevo servicio â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_nuevo:
    empleados = get_empleados()
    vehiculos = get_vehiculos()
    if not empleados or not vehiculos:
        st.warning("Necesitas al menos un empleado y un vehÃ­culo antes de crear un servicio.")
    else:
        with st.form("form_nuevo_srv"):
            st.subheader("Datos bÃ¡sicos")
            c1, c2, c3, c4 = st.columns(4)
            codigo      = c1.text_input("CÃ³digo *  (ej: SRV-025)")
            descripcion = c2.text_input("DescripciÃ³n *")
            zona        = c3.text_input("Zona / Localidad")
            dimension   = c4.text_input("DimensiÃ³n")

            c1, c2 = st.columns(2)
            fi_cont     = c1.date_input("Fecha inicio del servicio", value=hoy)
            tiene_fin_n = c2.checkbox("Â¿Tiene fecha de fin?", value=False, key="nuevo_tiene_fin")
            ff_cont     = None
            if tiene_fin_n:
                ff_cont = c2.date_input("Fecha fin del servicio", value=hoy, key="nuevo_ff")

            c1, c2 = st.columns(2)
            opts_emp = {f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados}
            opts_veh = {f"{v['matricula']} â€” {v['marca']} {v['modelo']}": v["id"] for v in vehiculos}
            emp_sel  = c1.selectbox("Empleado base *", list(opts_emp.keys()))
            veh_sel  = c2.selectbox("VehÃ­culo base *", list(opts_veh.keys()))

            st.subheader("Empresa cliente")
            c1, c2, c3 = st.columns(3)
            emp_nombre = c1.text_input("RazÃ³n social")
            emp_cif    = c2.text_input("CIF / NIF")
            emp_dir    = c3.text_input("DirecciÃ³n fiscal")
            c1, c2, c3 = st.columns(3)
            emp_cp     = c1.text_input("CÃ³digo postal")
            emp_ciudad = c2.text_input("Ciudad")
            emp_prov   = c3.text_input("Provincia")

            st.subheader("Contacto principal")
            c1, c2, c3, c4 = st.columns(4)
            ct_nombre = c1.text_input("Nombre")
            ct_cargo  = c2.text_input("Cargo")
            ct_email  = c3.text_input("Email")
            ct_tel    = c4.text_input("TelÃ©fono")

            st.subheader("FacturaciÃ³n")
            c1, c2, c3 = st.columns(3)
            fac_email  = c1.text_input("Email facturaciÃ³n")
            fac_pago   = c2.selectbox("Forma de pago", FORMAS_PAGO)

            if st.form_submit_button("Crear servicio", type="primary"):
                if not codigo or not descripcion:
                    st.error("CÃ³digo y descripciÃ³n son obligatorios.")
                else:
                    try:
                        get_supabase().table("servicios").insert({
                            "codigo": codigo, "descripcion": descripcion, "zona": n(zona),
                            "dimension": n(dimension),
                            "fecha_inicio_contrato": str(fi_cont),
                            "fecha_fin_contrato": str(ff_cont) if ff_cont else None,
                            "empleado_base_id": opts_emp[emp_sel],
                            "vehiculo_base_id": opts_veh[veh_sel],
                            "empresa_nombre": n(emp_nombre), "empresa_cif": n(emp_cif),
                            "empresa_direccion": n(emp_dir), "empresa_cp": n(emp_cp),
                            "empresa_ciudad": n(emp_ciudad), "empresa_provincia": n(emp_prov),
                            "contacto_nombre": n(ct_nombre), "contacto_cargo": n(ct_cargo),
                            "contacto_email": n(ct_email), "contacto_telefono": n(ct_tel),
                            "facturacion_email": n(fac_email), "facturacion_forma_pago": n(fac_pago),
                            "activo": True,
                        }).execute()
                        st.success(f"Servicio **{codigo}** creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

# â”€â”€ Importar desde Excel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_importar:
    st.markdown("### Importar servicios desde la plantilla Excel")
    st.info("Sube la plantilla rellena. Se crearÃ¡n los servicios que no existan (por cÃ³digo). "
            "Los que ya existan se actualizarÃ¡n.")

    archivo = st.file_uploader("Selecciona PLANTILLA_SERVICIOS.xlsx",
                               type=["xlsx"], key="uploader_servicios")

    if archivo:
        def limpio(val):
            s = str(val).strip()
            return None if s in ('nan', '', 'None', 'NaN') else s

        def a_fecha(val):
            if limpio(str(val)) is None:
                return None
            try:
                if isinstance(val, date):
                    return str(val)
                return pd.to_datetime(val, dayfirst=True).strftime('%Y-%m-%d')
            except Exception:
                return None

        try:
            df = pd.read_excel(archivo, sheet_name="Servicios", header=1, dtype=str)
            # Quitar fila de ejemplo si existe
            df = df[~df.apply(lambda r: r.astype(str).str.contains("EJEMPLO", case=False).any(), axis=1)]
            df = df.dropna(subset=["codigo"])
            df = df[df["codigo"].str.strip().str.upper() != "CODIGO"]

            st.write(f"**{len(df)} servicios encontrados en el archivo:**")
            st.dataframe(df[["codigo","descripcion","zona","dimension",
                              "empresa_nombre","contacto_nombre"]].fillna(""),
                         use_container_width=True, hide_index=True)

            if st.button("â¬†ï¸ Importar a Supabase", type="primary"):
                sb = get_supabase()
                ok = err = act = 0
                errores = []

                for _, row in df.iterrows():
                    cod = limpio(row.get("codigo"))
                    if not cod:
                        continue
                    datos = {
                        "codigo":                 cod,
                        "descripcion":            limpio(row.get("descripcion")) or cod,
                        "zona":                   limpio(row.get("zona")),
                        "dimension":              limpio(row.get("dimension")),
                        "fecha_inicio_contrato":  a_fecha(row.get("fecha_inicio_contrato")),
                        "fecha_fin_contrato":     a_fecha(row.get("fecha_fin_contrato")),
                        "empresa_nombre":         limpio(row.get("empresa_nombre")),
                        "empresa_cif":            limpio(row.get("empresa_cif")),
                        "empresa_direccion":      limpio(row.get("empresa_direccion")),
                        "empresa_cp":             limpio(row.get("empresa_cp")),
                        "empresa_ciudad":         limpio(row.get("empresa_ciudad")),
                        "empresa_provincia":      limpio(row.get("empresa_provincia")),
                        "empresa_pais":           limpio(row.get("empresa_pais")) or "EspaÃ±a",
                        "contacto_nombre":        limpio(row.get("contacto_nombre")),
                        "contacto_cargo":         limpio(row.get("contacto_cargo")),
                        "contacto_email":         limpio(row.get("contacto_email")),
                        "contacto_telefono":      limpio(row.get("contacto_telefono")),
                        "contacto_movil":         limpio(row.get("contacto_movil")),
                        "contacto2_nombre":       limpio(row.get("contacto2_nombre")),
                        "contacto2_email":        limpio(row.get("contacto2_email")),
                        "contacto2_telefono":     limpio(row.get("contacto2_telefono")),
                        "facturacion_email":      limpio(row.get("facturacion_email")),
                        "facturacion_forma_pago": limpio(row.get("facturacion_forma_pago")),
                        "observaciones":          limpio(row.get("observaciones")),
                        "activo": True,
                    }
                    try:
                        existe = sb.table("servicios").select("id").eq("codigo", cod).execute()
                        if existe.data:
                            sb.table("servicios").update(datos).eq("codigo", cod).execute()
                            act += 1
                        else:
                            sb.table("servicios").insert(datos).execute()
                            ok += 1
                    except Exception as e:
                        err += 1
                        errores.append(f"{cod}: {e}")

                if ok:   st.success(f"âœ… {ok} servicio(s) creados.")
                if act:  st.info(f"ðŸ”„ {act} servicio(s) actualizados.")
                if err:  st.error(f"âŒ {err} error(s):")
                for e in errores:
                    st.caption(e)
                if ok + act > 0:
                    st.warning("âš ï¸ Recuerda asignar el **empleado** y **vehÃ­culo** a cada servicio desde la ficha.")
                    st.rerun()

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            st.caption("AsegÃºrate de que la hoja se llama 'Servicios' y el formato es correcto.")


