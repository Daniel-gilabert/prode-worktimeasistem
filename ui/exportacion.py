import streamlit as st
from services.informe_pdf_service import InformePDFService
from services.informe_excel_service import InformeExcelService

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def render_exportacion(
    resumen_global: list[dict],
    mes: int,
    anno: int,
    logo_path: str | None = None,
) -> None:
    if not resumen_global:
        return

    nombre_mes = MESES_ES.get(mes, str(mes))
    st.divider()
    st.subheader("Exportar informes")

    pdf_svc = InformePDFService(logo_path=logo_path)
    xls_svc = InformeExcelService()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        pdf_global = pdf_svc.generar_pdf_global(resumen_global, mes, anno)
        st.download_button(
            label="PDF global",
            data=pdf_global,
            file_name=f"informe_global_{nombre_mes}_{anno}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with col2:
        xls_global = xls_svc.generar_excel_global(resumen_global, mes, anno)
        st.download_button(
            label="Excel global",
            data=xls_global,
            file_name=f"informe_global_{nombre_mes}_{anno}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.markdown("##### Informes individuales")
    for emp_data in resumen_global:
        nombre_safe = emp_data["nombre"].replace(" ", "_")
        c1, c2 = st.columns(2)
        with c1:
            pdf_ind = pdf_svc.generar_pdf_individual(emp_data, mes, anno)
            st.download_button(
                label=f"PDF — {emp_data['nombre']}",
                data=pdf_ind,
                file_name=f"informe_{nombre_safe}_{nombre_mes}_{anno}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"pdf_ind_{emp_data['id']}",
            )
        with c2:
            xls_ind = xls_svc.generar_excel_individual(emp_data, mes, anno)
            st.download_button(
                label=f"Excel — {emp_data['nombre']}",
                data=xls_ind,
                file_name=f"informe_{nombre_safe}_{nombre_mes}_{anno}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"xls_ind_{emp_data['id']}",
            )
