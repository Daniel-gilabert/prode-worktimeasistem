import streamlit as st
from datetime import date
from core.queries import get_servicios, get_empleados, get_vehiculos, calcular_estado_servicio
from core.documentos import get_documentos, subir_documento, borrar_documento, TIPOS_DOCUMENTO, get_icono_tipo
from core.db import get_supabase

st.set_page_config(page_title="Servicios", layout="wide")
st.title("Servicios")

tab_lista, tab_ficha, tab_nuevo = st.tabs([
    "Lista de servicios", "Ficha completa", "Nuevo servicio"
])

hoy = date.today()

ESTADO_BADGE = {
    "OPERATIVO":    ("🟢", "#DCFCE7", "#166534"),
    "EN_RIESGO":    ("🟡", "#FEF9C3", "#854D0E"),
    "NO_OPERATIVO": ("🔴", "#FEE2E2", "#991B1B"),
}

FORMAS_PAGO = ["Transferencia", "Confirming", "Remesa"]

# ── Lista de servicios ────────────────────────────────────────────
with tab_lista:
    fecha   = st.date_input("Ver estado para:", value=hoy, key="fecha_lista")
    servicios = get_servicios()

    if not servicios:
        st.info("No hay servicios registrados. Créalos en la pestaña 'Nuevo servicio'.")
    else:
        for s in servicios:
            try:
                estado = calcular_estado_servicio(s, fecha)
                ico, bg, fg = ESTADO_BADGE[estado.estado]
            except Exception:
                ico, bg, fg, estado = "⚪", "#F3F4F6", "#374151", None

            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2.5, 2, 2, 1.5, 1.5])
                with c1:
                    st.markdown(f"**`{s['codigo']}`**")
                    if s.get("zona"):
                        st.caption(s["zona"])
                with c2:
                    st.write(s["descripcion"])
                    if s.get("empresa_nombre"):
                        st.caption(f"🏢 {s['empresa_nombre']}")
                with c3:
                    st.write(f"👤 {s['empleado_base_nombre']}")
                with c4:
                    st.write(f"🚐 `{s['vehiculo_base_matricula']}`")
                with c5:
                    st.markdown(
                        f"<span style='background:{bg};color:{fg};padding:3px 10px;"
                        f"border-radius:99px;font-size:.8rem;font-weight:600'>"
                        f"{ico} {estado.estado.replace('_',' ') if estado else '—'}</span>",
                        unsafe_allow_html=True
                    )
                with c6:
                    if st.button("Ver ficha", key=f"ficha_{s['id']}"):
                        st.session_state["servicio_seleccionado"] = s["id"]
                        st.rerun()

# ── Ficha completa del servicio ───────────────────────────────────
with tab_ficha:
    servicios  = get_servicios()
    if not servicios:
        st.info("No hay servicios creados todavía.")
        st.stop()

    opts       = {f"{s['codigo']} — {s['descripcion']}": s for s in servicios}
    default    = 0
    srv_id_sel = st.session_state.get("servicio_seleccionado")
    if srv_id_sel:
        match = next((i for i, s in enumerate(servicios) if s["id"] == srv_id_sel), 0)
        default = match

    sel = st.selectbox("Selecciona servicio", list(opts.keys()), index=default, key="sel_ficha")
    srv = opts[sel]

    # Estado operativo
    try:
        estado = calcular_estado_servicio(srv, hoy)
        ico, bg, fg = ESTADO_BADGE[estado.estado]
        st.markdown(
            f"<div style='background:{bg};color:{fg};padding:10px 18px;border-radius:10px;"
            f"font-weight:600;font-size:1rem;margin-bottom:12px'>"
            f"{ico} Estado hoy: {estado.estado.replace('_',' ')}"
            + (f" — {' | '.join(m.descripcion for m in estado.motivos)}" if estado.motivos else "")
            + "</div>",
            unsafe_allow_html=True
        )
    except Exception as e:
        st.warning(f"No se pudo calcular estado: {e}")

    # ── Formulario de edición ─────────────────────────────────
    with st.expander("✏️ Editar datos del servicio", expanded=False):
        empleados = get_empleados()
        vehiculos = get_vehiculos()
        opts_emp  = {f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados}
        opts_veh  = {f"{v['matricula']} — {v['marca']} {v['modelo']}": v["id"] for v in vehiculos}
        idx_emp   = list(opts_emp.values()).index(srv["empleado_base_id"]) if srv["empleado_base_id"] in opts_emp.values() else 0
        idx_veh   = list(opts_veh.values()).index(srv["vehiculo_base_id"]) if srv["vehiculo_base_id"] in opts_veh.values() else 0

        with st.form("form_editar_srv"):
            st.subheader("Datos básicos")
            c1, c2, c3 = st.columns(3)
            codigo      = c1.text_input("Código",      value=srv.get("codigo",""))
            descripcion = c2.text_input("Descripción", value=srv.get("descripcion",""))
            zona        = c3.text_input("Zona",        value=srv.get("zona","") or "")

            c1, c2 = st.columns(2)
            fi_str = srv.get("fecha_inicio_contrato","")
            ff_str = srv.get("fecha_fin_contrato","")
            fi_val = date.fromisoformat(str(fi_str)[:10]) if fi_str else hoy
            ff_val = date.fromisoformat(str(ff_str)[:10]) if ff_str else None
            fi_cont = c1.date_input("Fecha inicio del servicio", value=fi_val)
            ff_cont = c2.date_input("Fecha fin del servicio (opcional)", value=ff_val or fi_val)

            st.subheader("Recursos asignados")
            c1, c2 = st.columns(2)
            emp_sel = c1.selectbox("Empleado base", list(opts_emp.keys()), index=idx_emp)
            veh_sel = c2.selectbox("Vehículo base", list(opts_veh.keys()), index=idx_veh)

            st.subheader("Datos empresa cliente")
            c1, c2, c3 = st.columns(3)
            emp_nombre = c1.text_input("Razón social",  value=srv.get("empresa_nombre","") or "")
            emp_cif    = c2.text_input("CIF / NIF",     value=srv.get("empresa_cif","") or "")
            emp_pais   = c3.text_input("País",          value=srv.get("empresa_pais","España") or "España")
            emp_dir    = st.text_input("Dirección fiscal", value=srv.get("empresa_direccion","") or "")
            c1, c2, c3 = st.columns(3)
            emp_cp     = c1.text_input("Código postal", value=srv.get("empresa_cp","") or "")
            emp_ciudad = c2.text_input("Ciudad",        value=srv.get("empresa_ciudad","") or "")
            emp_prov   = c3.text_input("Provincia",     value=srv.get("empresa_provincia","") or "")

            st.subheader("Contacto principal")
            c1, c2 = st.columns(2)
            ct_nombre  = c1.text_input("Nombre contacto",   value=srv.get("contacto_nombre","") or "", key="e_ct_nombre")
            ct_cargo   = c2.text_input("Cargo",             value=srv.get("contacto_cargo","") or "",  key="e_ct_cargo")
            c1, c2, c3 = st.columns(3)
            ct_email   = c1.text_input("Email principal",   value=srv.get("contacto_email","") or "",  key="e_ct_email")
            ct_tel     = c2.text_input("Teléfono principal",value=srv.get("contacto_telefono","") or "",key="e_ct_tel")
            ct_movil   = c3.text_input("Móvil",             value=srv.get("contacto_movil","") or "",  key="e_ct_movil")

            st.subheader("Contacto secundario")
            c1, c2, c3 = st.columns(3)
            ct2_nombre = c1.text_input("Nombre secundario", value=srv.get("contacto2_nombre","") or "", key="e_ct2_nombre")
            ct2_email  = c2.text_input("Email secundario",  value=srv.get("contacto2_email","") or "",  key="e_ct2_email")
            ct2_tel    = c3.text_input("Teléfono secundario",value=srv.get("contacto2_telefono","") or "",key="e_ct2_tel")

            st.subheader("Facturación")
            c1, c2, c3 = st.columns(3)
            fac_email  = c1.text_input("Email facturación", value=srv.get("facturacion_email","") or "", key="e_fac_email")

            fp_actual = srv.get("facturacion_forma_pago","") or ""
            fp_idx = FORMAS_PAGO.index(fp_actual) if fp_actual in FORMAS_PAGO else 0
            fac_pago   = c2.selectbox("Forma de pago", FORMAS_PAGO, index=fp_idx)

            num_cuenta = c3.text_input("Número de cuenta (IBAN)", value=srv.get("numero_cuenta","") or "")

            obs = st.text_area("Observaciones", value=srv.get("observaciones","") or "")

            if st.form_submit_button("💾 Guardar cambios", type="primary"):
                def n(v): return v if v else None
                try:
                    get_supabase().table("servicios").update({
                        "codigo": codigo, "descripcion": descripcion, "zona": n(zona),
                        "fecha_inicio_contrato": str(fi_cont),
                        "fecha_fin_contrato": str(ff_cont) if ff_cont else None,
                        "empleado_base_id": opts_emp[emp_sel],
                        "vehiculo_base_id": opts_veh[veh_sel],
                        "empresa_nombre": n(emp_nombre), "empresa_cif": n(emp_cif),
                        "empresa_direccion": n(emp_dir), "empresa_cp": n(emp_cp),
                        "empresa_ciudad": n(emp_ciudad), "empresa_provincia": n(emp_prov),
                        "empresa_pais": emp_pais or "España",
                        "contacto_nombre": n(ct_nombre), "contacto_cargo": n(ct_cargo),
                        "contacto_email": n(ct_email), "contacto_telefono": n(ct_tel),
                        "contacto_movil": n(ct_movil),
                        "contacto2_nombre": n(ct2_nombre), "contacto2_email": n(ct2_email),
                        "contacto2_telefono": n(ct2_tel),
                        "facturacion_email": n(fac_email), "facturacion_forma_pago": n(fac_pago),
                        "numero_cuenta": n(num_cuenta),
                        "observaciones": n(obs),
                    }).eq("id", srv["id"]).execute()
                    st.success("Servicio actualizado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Vista de datos actuales ───────────────────────────────
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 🏢 Empresa cliente")
        st.write(f"**{srv.get('empresa_nombre') or '—'}**")
        st.write(f"CIF: `{srv.get('empresa_cif') or '—'}`")
        st.write(f"{srv.get('empresa_direccion') or '—'}")
        st.write(f"{srv.get('empresa_cp') or ''} {srv.get('empresa_ciudad') or ''} ({srv.get('empresa_provincia') or '—'})")
        st.write(f"{srv.get('empresa_pais') or '—'}")
    with c2:
        st.markdown("#### 📞 Contactos")
        st.write(f"**{srv.get('contacto_nombre') or '—'}**")
        st.write(f"{srv.get('contacto_cargo') or '—'}")
        if srv.get("contacto_email"):
            st.write(f"✉️ {srv['contacto_email']}")
        if srv.get("contacto_telefono"):
            st.write(f"📞 {srv['contacto_telefono']}")
        if srv.get("contacto_movil"):
            st.write(f"📱 {srv['contacto_movil']}")
        if srv.get("contacto2_nombre"):
            st.markdown("**Contacto secundario:**")
            st.write(f"{srv['contacto2_nombre']}")
            if srv.get("contacto2_email"):
                st.write(f"✉️ {srv['contacto2_email']}")
            if srv.get("contacto2_telefono"):
                st.write(f"📞 {srv['contacto2_telefono']}")
    with c3:
        st.markdown("#### 📋 Datos del servicio")
        st.write(f"Inicio: {srv.get('fecha_inicio_contrato') or '—'}")
        if srv.get("fecha_fin_contrato"):
            st.write(f"Fin: {srv['fecha_fin_contrato']}")
        if srv.get("facturacion_email"):
            st.write(f"Facturación: {srv['facturacion_email']}")
        if srv.get("facturacion_forma_pago"):
            st.write(f"Pago: **{srv['facturacion_forma_pago']}**")
        if srv.get("numero_cuenta"):
            st.write(f"IBAN: `{srv['numero_cuenta']}`")
        if srv.get("observaciones"):
            st.caption(f"📌 {srv['observaciones']}")

    # ── Repositorio de documentos ─────────────────────────────
    st.divider()
    st.markdown("#### 📁 Documentos del servicio")

    try:
        docs = get_documentos(srv["id"])
        tabla_docs_ok = True
    except Exception:
        docs = []
        tabla_docs_ok = False

    if not tabla_docs_ok:
        st.warning(
            "La tabla de documentos no existe todavía en Supabase. "
            "Ejecuta el script `db/documentos.sql` en el SQL Editor de Supabase para activar esta función."
        )
    else:
        # Subir nuevo documento
        with st.expander("➕ Subir nuevo documento", expanded=len(docs) == 0):
            with st.form("form_doc"):
                c1, c2 = st.columns(2)
                doc_nombre = c1.text_input("Nombre del documento *")
                doc_tipo   = c2.selectbox("Tipo *", TIPOS_DOCUMENTO)
                doc_desc   = st.text_input("Descripción (opcional)")
                archivo    = st.file_uploader(
                    "Selecciona archivo (PDF, Word, Excel, imagen...)",
                    type=["pdf","doc","docx","xls","xlsx","jpg","jpeg","png","txt","zip"]
                )
                if st.form_submit_button("📤 Subir documento", type="primary"):
                    if not doc_nombre:
                        st.error("El nombre es obligatorio.")
                    elif not archivo:
                        st.error("Selecciona un archivo.")
                    else:
                        with st.spinner("Subiendo..."):
                            try:
                                subir_documento(
                                    servicio_id   = srv["id"],
                                    nombre        = doc_nombre,
                                    tipo          = doc_tipo,
                                    archivo_bytes = archivo.read(),
                                    nombre_archivo= archivo.name,
                                    descripcion   = doc_desc or None,
                                )
                                st.success(f"Documento **{doc_nombre}** subido.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al subir: {e}")

        if not docs:
            st.info("No hay documentos todavía. Usa el botón de arriba para subir el primero.")
        else:
            st.write(f"**{len(docs)} documento(s)**")
            TIPO_COLORES = {
                "Contrato":                ("📜", "#EDE9FE", "#4C1D95"),
                "Seguro vehículo":         ("🛡️", "#DCFCE7", "#166534"),
                "Permiso / Autorización":  ("✅", "#FEF9C3", "#854D0E"),
                "Factura":                 ("💶", "#FEE2E2", "#991B1B"),
                "Parte de trabajo":        ("📋", "#E0F2FE", "#0C4A6E"),
                "Ficha técnica vehículo":  ("🔧", "#F3F4F6", "#374151"),
                "Documentación empleado":  ("👤", "#FEF3C7", "#92400E"),
                "Acuerdo de servicio":     ("🤝", "#F0FDF4", "#14532D"),
                "Otro":                    ("📎", "#F9FAFB", "#4B5563"),
            }
            for doc in docs:
                ico_tipo, bg, fg = TIPO_COLORES.get(doc["tipo"], ("📎", "#F9FAFB", "#4B5563"))
                ico_archivo = get_icono_tipo(doc["nombre_archivo"])
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([0.4, 2.5, 1.5, 2, 1.2])
                    c1.markdown(f"<div style='font-size:1.5rem;text-align:center'>{ico_archivo}</div>",
                                unsafe_allow_html=True)
                    with c2:
                        st.write(f"**{doc['nombre']}**")
                        if doc.get("descripcion"):
                            st.caption(doc["descripcion"])
                    c3.markdown(
                        f"<span style='background:{bg};color:{fg};padding:2px 8px;"
                        f"border-radius:6px;font-size:.75rem'>{ico_tipo} {doc['tipo']}</span>",
                        unsafe_allow_html=True
                    )
                    c4.caption(f"Subido: {str(doc['fecha_subida'])[:10]}")
                    with c5:
                        if doc.get("url_publica"):
                            st.link_button("⬇️ Descargar", doc["url_publica"])
                        if st.button("🗑️", key=f"del_doc_{doc['id']}", help="Eliminar documento"):
                            borrar_documento(doc["id"], doc["storage_path"])
                            st.success("Documento eliminado.")
                            st.rerun()

# ── Nuevo servicio ────────────────────────────────────────────────
with tab_nuevo:
    empleados = get_empleados()
    vehiculos = get_vehiculos()
    if not empleados or not vehiculos:
        st.warning("Necesitas al menos un empleado y un vehículo antes de crear un servicio.")
    else:
        with st.form("form_nuevo_srv"):
            st.subheader("Datos básicos")
            c1, c2, c3 = st.columns(3)
            codigo      = c1.text_input("Código *  (ej: SRV-025)")
            descripcion = c2.text_input("Descripción *")
            zona        = c3.text_input("Zona / Localidad")

            c1, c2 = st.columns(2)
            fi_cont = c1.date_input("Fecha inicio del servicio", value=hoy)
            ff_cont = c2.date_input("Fecha fin del servicio (opcional)", value=hoy)

            c1, c2 = st.columns(2)
            opts_emp = {f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados}
            opts_veh = {f"{v['matricula']} — {v['marca']} {v['modelo']}": v["id"] for v in vehiculos}
            emp_sel  = c1.selectbox("Empleado base *", list(opts_emp.keys()))
            veh_sel  = c2.selectbox("Vehículo base *", list(opts_veh.keys()))

            st.subheader("Empresa cliente")
            c1, c2, c3 = st.columns(3)
            emp_nombre = c1.text_input("Razón social")
            emp_cif    = c2.text_input("CIF / NIF")
            emp_dir    = c3.text_input("Dirección fiscal")
            c1, c2, c3 = st.columns(3)
            emp_cp     = c1.text_input("Código postal")
            emp_ciudad = c2.text_input("Ciudad")
            emp_prov   = c3.text_input("Provincia")

            st.subheader("Contacto principal")
            c1, c2, c3, c4 = st.columns(4)
            ct_nombre = c1.text_input("Nombre")
            ct_cargo  = c2.text_input("Cargo")
            ct_email  = c3.text_input("Email")
            ct_tel    = c4.text_input("Teléfono")

            st.subheader("Facturación")
            c1, c2, c3 = st.columns(3)
            fac_email  = c1.text_input("Email facturación")
            fac_pago   = c2.selectbox("Forma de pago", FORMAS_PAGO)
            num_cuenta = c3.text_input("Número de cuenta (IBAN)")

            if st.form_submit_button("Crear servicio", type="primary"):
                if not codigo or not descripcion:
                    st.error("Código y descripción son obligatorios.")
                else:
                    def n(v): return v if v else None
                    try:
                        get_supabase().table("servicios").insert({
                            "codigo": codigo, "descripcion": descripcion, "zona": n(zona),
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
                            "numero_cuenta": n(num_cuenta),
                            "activo": True,
                        }).execute()
                        st.success(f"Servicio **{codigo}** creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
