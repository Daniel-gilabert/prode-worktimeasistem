import streamlit as st
from core.auth import check_login

from core.queries import get_vehiculos, actualizar_vehiculo, get_incidencias, crear_incidencia, cerrar_incidencia
from core.fotos import subir_foto_marca, get_fotos_marcas
from datetime import date

st.set_page_config(page_title="VehÃ­culos", layout="wide")

check_login()
st.title("VehÃ­culos")

hoy = date.today()

def _estado_fecha(fecha_str):
    if fecha_str is None:
        return "Sin fecha", "ðŸ”˜"
    try:
        d    = date.fromisoformat(str(fecha_str)[:10])
        dias = (d - hoy).days
        if dias < 0:   return f"VENCIDA Â· {d.strftime('%d/%m/%Y')}", "ðŸ”´"
        if dias <= 30: return f"Vence en {dias}d Â· {d.strftime('%d/%m/%Y')}", "ðŸŸ¡"
        return d.strftime("%d/%m/%Y"), "ðŸŸ¢"
    except Exception:
        return str(fecha_str), "âšª"

tab_lista, tab_itv_seguro, tab_incidencias, tab_fotos_marca = st.tabs([
    "Lista de vehÃ­culos", "Actualizar ITV / Seguro", "Incidencias", "ðŸ“· Fotos por marca"
])

# â”€â”€ Lista â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_lista:
    vehiculos    = get_vehiculos()
    fotos_marcas = get_fotos_marcas()
    st.write(f"**{len(vehiculos)} vehÃ­culos** en flota")

    col_filtro, _ = st.columns([2, 5])
    with col_filtro:
        filtro_marca = st.selectbox("Filtrar por marca",
            ["Todas"] + sorted(set(v["marca"] for v in vehiculos if v.get("marca"))))

    lista = vehiculos if filtro_marca == "Todas" else [v for v in vehiculos if v.get("marca") == filtro_marca]

    for v in lista:
        itv_txt, itv_ico = _estado_fecha(v.get("itv_vigente_hasta"))
        seg_txt, seg_ico = _estado_fecha(v.get("seguro_vigente_hasta"))
        foto_url         = fotos_marcas.get(v.get("marca", ""))

        with st.container(border=True):
            col_foto, col_datos = st.columns([1, 10])
            with col_foto:
                if foto_url:
                    st.image(foto_url, width=72)
                else:
                    st.markdown(
                        "<div style='width:72px;height:52px;border-radius:8px;"
                        "background:#F1F5F9;display:flex;align-items:center;"
                        "justify-content:center;font-size:28px;'>ðŸš</div>",
                        unsafe_allow_html=True
                    )
            with col_datos:
                c1, c2, c3, c4, c5, c6 = st.columns([1, 1.5, 2, 1.2, 2.2, 2.2])
                c1.markdown(f"**#{v.get('id_vehiculo','')}**")
                c2.markdown(f"**`{v['matricula']}`**")
                c3.write(f"{v['marca']} {v['modelo']}")
                c4.caption(v.get("tipo", ""))
                c5.write(f"ITV: {itv_ico} {itv_txt}")
                c6.write(f"Seguro: {seg_ico} {seg_txt}")

# â”€â”€ Actualizar ITV / Seguro â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_itv_seguro:
    vehiculos = get_vehiculos()
    opts = {f"{v['matricula']} â€” {v['marca']} {v['modelo']}": v for v in vehiculos}
    sel  = st.selectbox("Selecciona vehÃ­culo", list(opts.keys()))
    veh  = opts[sel]

    itv_actual = date.fromisoformat(str(veh["itv_vigente_hasta"])[:10]) if veh.get("itv_vigente_hasta") else None
    seg_actual = date.fromisoformat(str(veh["seguro_vigente_hasta"])[:10]) if veh.get("seguro_vigente_hasta") else None

    with st.form("form_itv_seguro"):
        c1, c2 = st.columns(2)
        with c1:
            nueva_itv = st.date_input("ITV vÃ¡lida hasta *", value=itv_actual or hoy)
        with c2:
            nuevo_seg = st.date_input("Seguro vÃ¡lido hasta *", value=seg_actual or hoy)
        bastidor    = st.text_input("Bastidor",    value=veh.get("bastidor") or "")
        aseguradora = st.text_input("Aseguradora", value=veh.get("aseguradora") or "")
        poliza      = st.text_input("NÂº PÃ³liza",   value=veh.get("poliza") or "")
        submitted = st.form_submit_button("Guardar cambios", type="primary")
        if submitted:
            try:
                actualizar_vehiculo(veh["id"], nueva_itv, nuevo_seg, bastidor or None,
                                    aseguradora or None, poliza or None)
                st.success(f"VehÃ­culo **{veh['matricula']}** actualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# â”€â”€ Incidencias â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_incidencias:
    vehiculos = get_vehiculos()
    st.subheader("Registrar incidencia")
    with st.form("form_incidencia"):
        opts = {f"{v['matricula']} â€” {v['marca']} {v['modelo']}": v["id"] for v in vehiculos}
        sel  = st.selectbox("VehÃ­culo *", list(opts.keys()))
        c1, c2 = st.columns(2)
        with c1:
            gravedad    = st.radio("Gravedad *", ["leve", "grave"], horizontal=True,
                                   help="Grave = vehÃ­culo fuera de servicio")
            fi          = st.date_input("Fecha inicio *", value=hoy)
        with c2:
            descripcion = st.text_area("DescripciÃ³n *", height=100)
            ya_resuelta = st.checkbox("Ya estÃ¡ resuelta")
            ff          = st.date_input("Fecha resoluciÃ³n", value=hoy) if ya_resuelta else None
        submitted = st.form_submit_button("Registrar", type="primary")
        if submitted:
            if not descripcion:
                st.error("La descripciÃ³n es obligatoria.")
            else:
                try:
                    crear_incidencia(opts[sel], gravedad, descripcion, fi, ff)
                    st.success("Incidencia registrada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.subheader("Incidencias abiertas")
    incidencias = get_incidencias()
    abiertas    = [i for i in incidencias if not i.get("fecha_fin")]
    if not abiertas:
        st.success("No hay incidencias abiertas.")
    else:
        for i in abiertas:
            veh_info = i.get("vehiculos") or {}
            mat      = veh_info.get("matricula", "â€”")
            ico      = "ðŸ”´" if i["gravedad"] == "grave" else "ðŸŸ¡"
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 1, 3, 2])
                c1.write(f"**`{mat}`**")
                c2.write(f"{ico} {i['gravedad'].capitalize()}")
                c3.write(i["descripcion"])
                c3.caption(f"Desde: {i['fecha_inicio']}")
                with c4:
                    if st.button(f"Cerrar #{i['id']}", key=f"c_{i['id']}"):
                        cerrar_incidencia(i["id"], hoy)
                        st.success("Incidencia cerrada.")
                        st.rerun()

    with st.expander("Ver historial de incidencias cerradas"):
        cerradas = [i for i in incidencias if i.get("fecha_fin")]
        if not cerradas:
            st.info("No hay incidencias cerradas.")
        for i in cerradas:
            veh_info = i.get("vehiculos") or {}
            mat      = veh_info.get("matricula", "â€”")
            ico      = "ðŸ”´" if i["gravedad"] == "grave" else "ðŸŸ¡"
            st.text(f"{ico} [{mat}] {i['fecha_inicio']} â†’ {i['fecha_fin']} | {i['descripcion']}")

# â”€â”€ Fotos por marca â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_fotos_marca:
    st.subheader("Foto representativa por marca de vehÃ­culo")
    st.info("Sube una foto por cada marca. Esa imagen aparecerÃ¡ en todos los vehÃ­culos de esa marca.")

    fotos_marcas = get_fotos_marcas()
    marcas       = list(fotos_marcas.keys())

    # Mostrar estado actual de las 3 marcas
    cols = st.columns(len(marcas))
    for col, marca in zip(cols, marcas):
        with col:
            url = fotos_marcas.get(marca)
            if url:
                st.image(url, caption=marca, width=120)
                st.success(f"âœ“ {marca}")
            else:
                st.markdown(
                    f"<div style='width:120px;height:80px;border-radius:8px;"
                    f"background:#F1F5F9;display:flex;align-items:center;"
                    f"justify-content:center;font-size:36px;'>ðŸš</div>",
                    unsafe_allow_html=True
                )
                st.warning(f"Sin foto â€” {marca}")

    st.divider()

    # Formulario de subida
    c1, c2 = st.columns([1, 2])
    with c1:
        marca_sel = st.selectbox("Marca *", marcas, key="sel_marca_foto")
    with c2:
        archivo = st.file_uploader(
            f"Foto para {marca_sel} (JPG, PNG)",
            type=["jpg", "jpeg", "png"],
            key=f"upload_marca_{marca_sel}"
        )

    if archivo:
        st.image(archivo, width=160, caption="Vista previa")
        if st.button("Subir foto de marca", type="primary"):
            with st.spinner("Subiendo..."):
                try:
                    ext = archivo.name.split(".")[-1].lower().replace("jpeg", "jpg")
                    subir_foto_marca(marca_sel, archivo.read(), ext)
                    st.success(f"Foto de **{marca_sel}** subida correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al subir: {e}")

