import logging
import os
from datetime import datetime, date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)

# ── Colores corporativos ─────────────────────────────────────────────────────
AZUL         = colors.HexColor("#1a3d6e")
AZUL_CLARO   = colors.HexColor("#e8f0fb")
AZUL_MED     = colors.HexColor("#2e6da4")
VERDE        = colors.HexColor("#d4edda")
VERDE_OSCURO = colors.HexColor("#28a745")
AMARILLO     = colors.HexColor("#fff3cd")
NARANJA      = colors.HexColor("#ffe5b4")
ROJO         = colors.HexColor("#f8d7da")
GRIS         = colors.HexColor("#e9ecef")
GRIS_OSCURO  = colors.HexColor("#6c757d")
AZUL_INC     = colors.HexColor("#cce5ff")
BLANCO       = colors.white

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

TIPO_COLOR = {
    "Laborable":        BLANCO,
    "Horas extra":      VERDE,
    "Sin fichar":       ROJO,
    "Error de registro":AMARILLO,
    "Festivo nacional": GRIS,
    "Festivo local":    GRIS,
    "Fin de semana":    GRIS,
    "Vacaciones":       AZUL_INC,
    "Baja médica":      AZUL_INC,
    "Permiso":          AZUL_INC,
    "Incidencia":       AZUL_INC,
}


def _hhmm(horas: float, con_signo: bool = False) -> str:
    neg = horas < 0
    h   = abs(horas)
    hh  = int(h)
    mm  = round((h - hh) * 60)
    if mm == 60:
        hh += 1; mm = 0
    txt = f"{hh}:{mm:02d}"
    if con_signo and not neg:
        return f"+{txt}"
    return f"-{txt}" if neg else txt


def _pie(canvas, doc):
    canvas.saveState()
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    ancho = doc.pagesize[0]
    canvas.drawString(2 * cm, 1.2 * cm,
        f"Generado el {fecha_emision} — WorkTimeAsistem PRODE — Desarrollado por Daniel Gilabert Cantero")
    canvas.drawRightString(ancho - 2 * cm, 1.2 * cm, f"Pág. {doc.page}")
    canvas.restoreState()


def _cabecera_elementos(logo_path, titulo, subtitulo):
    styles = getSampleStyleSheet()
    elementos = []
    t_style = ParagraphStyle("t", parent=styles["Normal"],
        fontSize=15, textColor=AZUL, fontName="Helvetica-Bold", alignment=TA_LEFT)
    s_style = ParagraphStyle("s", parent=styles["Normal"],
        fontSize=10, textColor=AZUL_MED, fontName="Helvetica", alignment=TA_LEFT)

    if logo_path and os.path.exists(logo_path):
        logo = Image(logo_path, width=3.5 * cm, height=1.5 * cm, hAlign="LEFT")
        col_txt = [[Paragraph(titulo, t_style), Spacer(1, 0.1*cm), Paragraph(subtitulo, s_style)]]
        t = Table([[logo, col_txt]], colWidths=[4.2*cm, None])
        t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        elementos.append(t)
    else:
        elementos.append(Paragraph(titulo, t_style))
        elementos.append(Spacer(1, 0.1*cm))
        elementos.append(Paragraph(subtitulo, s_style))

    elementos.append(Spacer(1, 0.3*cm))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=AZUL))
    elementos.append(Spacer(1, 0.4*cm))
    return elementos


class InformePDFService:
    def __init__(self, logo_path: str | None = None):
        self._logo = logo_path

    # ═══════════════════════════════════════════════════════════
    # PDF INDIVIDUAL
    # ═══════════════════════════════════════════════════════════
    def generar_pdf_individual(self, emp_data: dict, mes: int, anno: int) -> bytes:
        buffer  = BytesIO()
        nombre_mes = MESES_ES.get(mes, str(mes))
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=2*cm, bottomMargin=2.5*cm,
        )
        styles  = getSampleStyleSheet()
        elementos = []

        # ── Cabecera ──────────────────────────────────────────
        titulo    = f"Informe de Asistencia — {nombre_mes} {anno}"
        subtitulo = f"Empleado: {emp_data['nombre']}"
        elementos += _cabecera_elementos(self._logo, titulo, subtitulo)

        # ── Resumen stats (2 columnas x 3 filas) ──────────────
        stats = [
            ("Total horas mes",  _hhmm(emp_data["horas_reales"]) + " h"),
            ("Objetivo mensual", _hhmm(emp_data["objetivo"]) + " h"),
            ("Diferencia",       _hhmm(emp_data["diferencia"], con_signo=True) + " h"),
            ("Horas extra",      _hhmm(emp_data["horas_extra"]) + " h"),
            ("Días con fichaje", str(emp_data["fichados"])),
            ("Días sin fichaje", str(emp_data["sin_fichar"])),
        ]
        stat_style_key = ParagraphStyle("sk", parent=styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=AZUL)
        stat_style_val = ParagraphStyle("sv", parent=styles["Normal"],
            fontSize=9, fontName="Helvetica", textColor=colors.black)

        stats_filas = []
        for i in range(0, len(stats), 2):
            fila = []
            for k, v in stats[i:i+2]:
                fila += [Paragraph(k, stat_style_key), Paragraph(v, stat_style_val)]
            while len(fila) < 4:
                fila.append(Paragraph("", stat_style_val))
            stats_filas.append(fila)

        t_stats = Table(stats_filas, colWidths=[4.5*cm, 3*cm, 4.5*cm, 3*cm])
        t_stats.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), AZUL_CLARO),
            ("GRID",       (0,0), (-1,-1), 0.3, colors.lightgrey),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("ROUNDEDCORNERS", [4]),
        ]))
        elementos.append(t_stats)
        elementos.append(Spacer(1, 0.5*cm))

        # ── Tabla día a día ───────────────────────────────────
        dias = emp_data.get("dias", [])
        if dias:
            head_style = ParagraphStyle("h", parent=styles["Normal"],
                fontSize=8, fontName="Helvetica-Bold", textColor=BLANCO, alignment=TA_CENTER)
            cell_style = ParagraphStyle("c", parent=styles["Normal"],
                fontSize=8, fontName="Helvetica")

            encabezado = [
                Paragraph("Fecha", head_style),
                Paragraph("Horas", head_style),
                Paragraph("Tipo", head_style),
            ]
            filas_dias = [encabezado]
            estilos_dia = [
                ("BACKGROUND", (0,0), (-1,0), AZUL),
                ("TEXTCOLOR",  (0,0), (-1,0), BLANCO),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 8),
                ("ALIGN",      (0,0), (-1,-1), "CENTER"),
                ("ALIGN",      (2,1), (2,-1), "LEFT"),
                ("GRID",       (0,0), (-1,-1), 0.3, colors.lightgrey),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ]

            DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            for i, dia in enumerate(dias, start=1):
                d = dia["fecha"]
                dia_semana = DIAS_ES[d.weekday()]
                fecha_txt  = f"{dia_semana} {d.day:02d}/{d.month:02d}"
                horas_txt  = _hhmm(dia["horas"]) + " h" if dia["horas"] > 0 else "—"
                tipo_txt   = dia["tipo"]

                filas_dias.append([
                    Paragraph(fecha_txt, cell_style),
                    Paragraph(horas_txt, cell_style),
                    Paragraph(tipo_txt, cell_style),
                ])
                color_fila = TIPO_COLOR.get(tipo_txt, BLANCO)
                if color_fila != BLANCO:
                    estilos_dia.append(("BACKGROUND", (0,i), (-1,i), color_fila))

            t_dias = Table(filas_dias, colWidths=[3.5*cm, 2.8*cm, 8.7*cm])
            t_dias.setStyle(TableStyle(estilos_dia))
            elementos.append(Paragraph(
                "Detalle diario", ParagraphStyle("dh", parent=styles["Normal"],
                    fontSize=9, fontName="Helvetica-Bold", textColor=AZUL, spaceBefore=4)))
            elementos.append(Spacer(1, 0.2*cm))
            elementos.append(t_dias)
            elementos.append(Spacer(1, 0.4*cm))

        # ── Leyenda ───────────────────────────────────────────
        leyenda_items = [
            (VERDE,    "Horas extra (por encima del objetivo diario)"),
            (BLANCO,   "Laborable con fichaje correcto"),
            (AMARILLO, "Error de registro (entrada = salida)"),
            (ROJO,     "Sin fichar (día laborable sin registro)"),
            (AZUL_INC, "Ausencia justificada (Vacaciones / Baja / Permiso)"),
            (GRIS,     "Festivo o fin de semana"),
        ]
        ley_style = ParagraphStyle("l", parent=styles["Normal"], fontSize=7.5)
        ley_filas = []
        for col, txt in leyenda_items:
            ley_filas.append([Paragraph("", ley_style), Paragraph(txt, ley_style)])
        t_ley = Table(ley_filas, colWidths=[0.5*cm, 8*cm])
        ley_estilos = [
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]
        for i, (col, _) in enumerate(leyenda_items):
            ley_estilos.append(("BACKGROUND", (0,i), (0,i), col))
            ley_estilos.append(("BOX", (0,i), (0,i), 0.3, colors.grey))
        t_ley.setStyle(TableStyle(ley_estilos))
        elementos.append(Paragraph(
            "Leyenda de colores",
            ParagraphStyle("lh", parent=styles["Normal"],
                fontSize=8, fontName="Helvetica-Bold", textColor=AZUL_MED, spaceBefore=4)))
        elementos.append(Spacer(1, 0.15*cm))
        elementos.append(t_ley)

        doc.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
        logger.info("PDF individual generado: %s", emp_data["nombre"])
        return buffer.getvalue()

    # ═══════════════════════════════════════════════════════════
    # PDF GLOBAL
    # ═══════════════════════════════════════════════════════════
    def generar_pdf_global(self, lista_data: list[dict], mes: int, anno: int) -> bytes:
        buffer = BytesIO()
        nombre_mes = MESES_ES.get(mes, str(mes))
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2.5*cm,
        )
        styles    = getSampleStyleSheet()
        elementos = []

        titulo    = f"Resumen Global de Asistencia — {nombre_mes} {anno}"
        subtitulo = f"Fundación PRODE — Total empleados: {len(lista_data)}"
        elementos += _cabecera_elementos(self._logo, titulo, subtitulo)

        # ── Leyenda compacta ──────────────────────────────────
        ley_h = ParagraphStyle("lh2", parent=styles["Normal"],
            fontSize=8, fontName="Helvetica-Bold", textColor=AZUL_MED)
        ley_c = ParagraphStyle("lc2", parent=styles["Normal"], fontSize=8)
        leyenda_items_g = [
            (VERDE,    "Sin incidencias — fichaje completo"),
            (AMARILLO, "Atención — 1 o 2 días sin fichar"),
            (NARANJA,  "Alerta — 3 o 4 días sin fichar"),
            (ROJO,     "Crítico — 5 o más días sin fichar"),
        ]
        ley_g_data = [[
            Paragraph("■", ParagraphStyle("sq", parent=styles["Normal"],
                fontSize=10, textColor=c, fontName="Helvetica-Bold")),
            Paragraph(txt, ley_c),
        ] for c, txt in leyenda_items_g]
        t_leyg = Table([ley_g_data[i:i+2] for i in range(0, len(ley_g_data), 2)],
            colWidths=[0.5*cm, 7*cm, 0.5*cm, 7*cm])
        t_leyg.setStyle(TableStyle([
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))
        elementos.append(t_leyg)
        elementos.append(Spacer(1, 0.4*cm))

        # ── Tabla empleados ───────────────────────────────────
        head_s = ParagraphStyle("gh", parent=styles["Normal"],
            fontSize=8, fontName="Helvetica-Bold", textColor=BLANCO, alignment=TA_CENTER)
        cell_s = ParagraphStyle("gc", parent=styles["Normal"], fontSize=8)
        cell_c = ParagraphStyle("gcc", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER)

        encabezado = [
            Paragraph("Empleado", head_s),
            Paragraph("Jornada\n(h/sem)", head_s),
            Paragraph("Laborables", head_s),
            Paragraph("Fichados", head_s),
            Paragraph("Errores", head_s),
            Paragraph("Sin\nfichar", head_s),
            Paragraph("Horas\nreales", head_s),
            Paragraph("Objetivo\n(h)", head_s),
            Paragraph("Diferencia\n(h)", head_s),
            Paragraph("Extra\n(h)", head_s),
        ]
        filas = [encabezado]
        estilos_g = [
            ("BACKGROUND",    (0,0), (-1,0), AZUL),
            ("TEXTCOLOR",     (0,0), (-1,0), BLANCO),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("ALIGN",         (0,1), (0,-1), "LEFT"),
            ("GRID",          (0,0), (-1,-1), 0.3, colors.lightgrey),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [BLANCO, AZUL_CLARO]),
        ]

        for i, d in enumerate(sorted(lista_data, key=lambda x: x["nombre"]), start=1):
            sf = d["sin_fichar"]
            if sf == 0:
                bg = VERDE
            elif sf <= 2:
                bg = AMARILLO
            elif sf <= 4:
                bg = NARANJA
            else:
                bg = ROJO
            estilos_g.append(("BACKGROUND", (5,i), (5,i), bg))

            dif_txt = _hhmm(d["diferencia"], con_signo=True)
            filas.append([
                Paragraph(d["nombre"], cell_s),
                Paragraph(str(d["jornada"]), cell_c),
                Paragraph(str(d["laborables"]), cell_c),
                Paragraph(str(d["fichados"]), cell_c),
                Paragraph(str(d["errores"]), cell_c),
                Paragraph(str(d["sin_fichar"]), cell_c),
                Paragraph(_hhmm(d["horas_reales"]), cell_c),
                Paragraph(_hhmm(d["objetivo"]), cell_c),
                Paragraph(dif_txt, cell_c),
                Paragraph(_hhmm(d["horas_extra"]), cell_c),
            ])

        t_g = Table(filas,
            colWidths=[6*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.6*cm, 1.8*cm, 2.0*cm, 2.0*cm, 2.0*cm, 2.0*cm],
            repeatRows=1)
        t_g.setStyle(TableStyle(estilos_g))
        elementos.append(t_g)

        doc.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
        logger.info("PDF global generado: %d empleados", len(lista_data))
        return buffer.getvalue()
