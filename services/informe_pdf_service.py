import logging
import os
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)

COLOR_CORPORATIVO = colors.HexColor("#1a3d6e")
COLOR_SECUNDARIO = colors.HexColor("#e8f0fb")
COLOR_ACENTO = colors.HexColor("#2e6da4")
COLOR_EXITO = colors.HexColor("#d4edda")
COLOR_ALERTA = colors.HexColor("#ffe5b4")
COLOR_ERROR = colors.HexColor("#f8d7da")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _cabecera(logo_path: str | None, mes: int, anno: int) -> list:
    styles = getSampleStyleSheet()
    elementos = []

    titulo_style = ParagraphStyle(
        "titulo",
        parent=styles["Normal"],
        fontSize=16,
        textColor=COLOR_CORPORATIVO,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )
    subtitulo_style = ParagraphStyle(
        "subtitulo",
        parent=styles["Normal"],
        fontSize=11,
        textColor=COLOR_ACENTO,
        fontName="Helvetica",
        alignment=TA_LEFT,
    )

    nombre_mes = MESES_ES.get(mes, str(mes)).capitalize()
    titulo_texto = f"Informe de Control Horario — {nombre_mes} {anno}"
    subtitulo_texto = "Fundación PRODE — Departamento Última Milla"

    if logo_path and os.path.exists(logo_path):
        logo = Image(logo_path, width=4 * cm, height=1.8 * cm, hAlign="LEFT")
        titulo_col = [
            Paragraph(titulo_texto, titulo_style),
            Spacer(1, 0.1 * cm),
            Paragraph(subtitulo_texto, subtitulo_style),
        ]
        data = [[logo, titulo_col]]
        t = Table(data, colWidths=[5 * cm, 13 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elementos.append(t)
    else:
        elementos.append(Paragraph(titulo_texto, titulo_style))
        elementos.append(Spacer(1, 0.1 * cm))
        elementos.append(Paragraph(subtitulo_texto, subtitulo_style))

    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=COLOR_CORPORATIVO))
    elementos.append(Spacer(1, 0.4 * cm))
    return elementos


def _pie(canvas, doc):
    canvas.saveState()
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(
        2 * cm, 1.2 * cm,
        f"Documento generado el {fecha_emision} — WorkTimeAsistem PRODE"
    )
    ancho_pagina = doc.pagesize[0]
    canvas.drawRightString(
        ancho_pagina - 2 * cm, 1.2 * cm,
        f"Pág. {doc.page}"
    )
    canvas.restoreState()


def _tabla_resumen(datos: list[dict]) -> Table:
    encabezado = [
        "Empleado", "Jornada\n(h/sem)", "Laborables", "Fichados",
        "Errores", "Sin fichar", "Horas\nreales", "Objetivo\n(h)",
        "Diferencia\n(h)", "Extra\n(h)",
    ]
    filas = [encabezado]
    for d in datos:
        filas.append([
            d["nombre"],
            str(d["jornada"]),
            str(d["laborables"]),
            str(d["fichados"]),
            str(d["errores"]),
            str(d["sin_fichar"]),
            str(d["horas_reales"]),
            str(d["objetivo"]),
            str(d["diferencia"]),
            str(d["horas_extra"]),
        ])

    col_widths = [6.0*cm, 2.0*cm, 2.0*cm, 2.0*cm, 1.8*cm, 2.0*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm]
    t = Table(filas, colWidths=col_widths, repeatRows=1)

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_CORPORATIVO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_SECUNDARIO]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for i, d in enumerate(datos, start=1):
        if d["sin_fichar"] == 0:
            estilo.append(("BACKGROUND", (5, i), (5, i), COLOR_EXITO))
        elif d["sin_fichar"] < 3:
            estilo.append(("BACKGROUND", (5, i), (5, i), COLOR_ALERTA))
        else:
            estilo.append(("BACKGROUND", (5, i), (5, i), COLOR_ERROR))

    t.setStyle(TableStyle(estilo))
    return t


def _tabla_individual(d: dict) -> Table:
    filas = [
        ["Campo", "Valor"],
        ["Empleado", d["nombre"]],
        ["Jornada semanal", f"{d['jornada']} h"],
        ["Días laborables", str(d["laborables"])],
        ["Días fichados", str(d["fichados"])],
        ["Días con error", str(d["errores"])],
        ["Días sin fichar", str(d["sin_fichar"])],
        ["Horas reales", f"{d['horas_reales']} h"],
        ["Objetivo mensual", f"{d['objetivo']} h"],
        ["Diferencia", f"{d['diferencia']} h"],
        ["Horas extra", f"{d['horas_extra']} h"],
    ]

    t = Table(filas, colWidths=[6 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_CORPORATIVO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_SECUNDARIO]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


class InformePDFService:
    def __init__(self, logo_path: str | None = None):
        self._logo = logo_path

    def generar_pdf_global(self, lista_data: list[dict], mes: int, anno: int) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2.5 * cm,
        )
        styles = getSampleStyleSheet()
        elementos = _cabecera(self._logo, mes, anno)

        desc_style = ParagraphStyle(
            "desc", parent=styles["Normal"], fontSize=9, textColor=colors.grey
        )
        nombre_mes = MESES_ES.get(mes, str(mes)).capitalize()
        elementos.append(
            Paragraph(
                f"Resumen global de cumplimiento horario para {nombre_mes} de {anno}. "
                f"Total de empleados: {len(lista_data)}.",
                desc_style,
            )
        )
        elementos.append(Spacer(1, 0.5 * cm))
        elementos.append(_tabla_resumen(lista_data))

        doc.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
        logger.info("PDF global generado: %d empleados", len(lista_data))
        return buffer.getvalue()

    def generar_pdf_individual(self, emp_data: dict, mes: int, anno: int) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2.5 * cm,
        )
        styles = getSampleStyleSheet()
        elementos = _cabecera(self._logo, mes, anno)

        nombre_mes = MESES_ES.get(mes, str(mes)).capitalize()
        subtitulo_style = ParagraphStyle(
            "sub2",
            parent=styles["Normal"],
            fontSize=10,
            textColor=COLOR_CORPORATIVO,
            fontName="Helvetica-Bold",
        )
        elementos.append(
            Paragraph(
                f"Informe individual — {emp_data['nombre']} — {nombre_mes} {anno}",
                subtitulo_style,
            )
        )
        elementos.append(Spacer(1, 0.5 * cm))
        elementos.append(_tabla_individual(emp_data))

        doc.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
        logger.info("PDF individual generado: %s", emp_data["nombre"])
        return buffer.getvalue()
