import streamlit as st
from core.auth import check_login

from core.queries import get_empleados, crear_empleado, get_ausencias, crear_ausencia, hay_solapamiento_ausencia
from core.fotos import subir_foto_empleado
from datetime import date

st.set_page_config(page_title="Empleados", layout="wide")

check_login()
st.title("Empleados")

tab_lista, tab_nuevo, tab_ausencias, tab_fotos = st.tabs([
    "Lista", "Nuevo empleado", "Ausencias", "ðŸ“· Fotos"
])

# â”€â”€ Lista â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_lista:
    empleados = get_empleados()
    if not empleados:
        st.info("No hay empleados registrados.")
    else:
        st.write(f"**{len(empleados)} empleados** activos")
        for e in empleados:
            with st.container(border=True):
                col_foto, col_datos = st.columns([1, 8])
                with col_foto:
                    if e.get("foto_url"):
                        st.image(e["foto_url"], width=64)
                    else:
                        st.markdown(
                            "<div style='width:64px;height:64px;border-radius:50%;"
                            "background:#E2E8F0;display:flex;align-items:center;"
                            "justify-content:center;font-size:24px;'>ðŸ‘¤</div>",
                            unsafe_allow_html=True
                        )
                with col_datos:
                    c1, c2, c3, c4 = st.columns([2.5, 1.5, 1.5, 2])
                    c1.markdown(f"**{e['apellidos']}, {e['nombre']}**")
                    c2.write(f"`{e['dni']}`")
                    c3.write(e.get("telefono") or "â€”")
                    c4.write(e.get("email") or "â€”")

# â”€â”€ Nuevo empleado â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_nuevo:
    with st.form("form_empleado"):
        c1, c2 = st.columns(2)
        with c1:
            nombre    = st.text_input("Nombre *")
            apellidos = st.text_input("Apellidos *")
            dni       = st.text_input("DNI *")
        with c2:
            telefono = st.text_input("TelÃ©fono")
            email    = st.text_input("Email")
        submitted = st.form_submit_button("Crear empleado", type="primary")
        if submitted:
            if not nombre or not apellidos or not dni:
                st.error("Nombre, apellidos y DNI son obligatorios.")
            else:
                try:
                    crear_empleado(nombre, apellidos, dni, telefono, email)
                    st.success(f"Empleado **{nombre} {apellidos}** creado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# â”€â”€ Ausencias â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_ausencias:
    st.subheader("Registrar ausencia")
    empleados = get_empleados()
    with st.form("form_ausencia"):
        opts = {f"{e['apellidos']}, {e['nombre']}": e["id"] for e in empleados}
        sel  = st.selectbox("Empleado *", list(opts.keys()))
        c1, c2 = st.columns(2)
        with c1:
            fi   = st.date_input("Fecha inicio *", value=date.today())
            tipo = st.selectbox("Tipo *", ["baja", "vacaciones", "permiso", "otro"])
        with c2:
            ff  = st.date_input("Fecha fin *", value=date.today())
            obs = st.text_input("Observaciones")
        submitted = st.form_submit_button("Registrar ausencia", type="primary")
        if submitted:
            if ff < fi:
                st.error("La fecha fin no puede ser anterior a la fecha inicio.")
            elif hay_solapamiento_ausencia(opts[sel], fi, ff):
                st.error("Ya existe una ausencia de este empleado que se solapa en esas fechas.")
            else:
                try:
                    crear_ausencia(opts[sel], fi, ff, tipo, obs)
                    st.success("Ausencia registrada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.subheader("Ausencias registradas")
    ausencias = get_ausencias()
    if not ausencias:
        st.info("No hay ausencias registradas.")
    else:
        for a in ausencias:
            emp    = a.get("empleados") or {}
            nombre = f"{emp.get('apellidos','')}, {emp.get('nombre','')}" if emp else "â€”"
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2.5, 1.5, 1.5, 2])
                c1.write(f"**{nombre}**")
                c2.write(f"{a['fecha_inicio']} â†’ {a['fecha_fin']}")
                c3.write(a["tipo"])
                c4.caption(a.get("observaciones") or "â€”")

# â”€â”€ Fotos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with tab_fotos:
    st.subheader("Subir foto de empleado")
    st.info("La foto aparecerÃ¡ en la lista de empleados y en el dashboard.")
    empleados = get_empleados()
    opts = {f"{e['apellidos']}, {e['nombre']}": e for e in empleados}
    sel  = st.selectbox("Selecciona empleado", list(opts.keys()), key="sel_emp_foto")
    emp  = opts[sel]

    col_preview, col_upload = st.columns([1, 3])
    with col_preview:
        if emp.get("foto_url"):
            st.image(emp["foto_url"], width=120, caption="Foto actual")
        else:
            st.markdown(
                "<div style='width:120px;height:120px;border-radius:12px;"
                "background:#E2E8F0;display:flex;align-items:center;"
                "justify-content:center;font-size:48px;'>ðŸ‘¤</div>",
                unsafe_allow_html=True
            )
            st.caption("Sin foto")

    with col_upload:
        archivo = st.file_uploader(
            "Selecciona una foto (JPG, PNG)",
            type=["jpg", "jpeg", "png"],
            key="upload_emp_foto"
        )
        if archivo:
            st.image(archivo, width=120, caption="Vista previa")
            if st.button("Subir foto", type="primary"):
                with st.spinner("Subiendo..."):
                    try:
                        ext = archivo.name.split(".")[-1].lower().replace("jpeg", "jpg")
                        subir_foto_empleado(emp["id"], archivo.read(), ext)
                        st.success(f"Foto de **{emp['nombre']} {emp['apellidos']}** subida.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al subir: {e}")

