import calendar
import logging
import unicodedata
from datetime import date, timedelta
import pandas as pd
from models.empleado import Empleado

logger = logging.getLogger(__name__)


def _limpiar(txt: str) -> str:
    if not txt:
        return ""
    txt = str(txt).strip().upper()
    txt = unicodedata.normalize("NFD", txt)
    txt = txt.encode("ascii", "ignore").decode("utf-8")
    return " ".join(txt.split())


def _clave_sorted(txt: str) -> str:
    return " ".join(sorted(_limpiar(txt).split()))


FESTIVOS_NACIONALES_BASE = [
    (1, 1),   # Año Nuevo
    (1, 6),   # Reyes
    (2, 28),  # Día de Andalucía
    (5, 1),   # Día del Trabajo
    (8, 15),  # Asunción
    (10, 12), # Fiesta Nacional
    (11, 1),  # Todos los Santos
    (12, 6),  # Día de la Constitución
    (12, 8),  # Inmaculada
    (12, 25), # Navidad
]


def _festivos_nacionales(anno: int) -> set[date]:
    resultado = set()
    for mes, dia in FESTIVOS_NACIONALES_BASE:
        try:
            resultado.add(date(anno, mes, dia))
        except ValueError:
            pass
    return resultado


def _daterange(start: date, end: date):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)


class CalculoService:
    def calcular_resumen_empleado(
        self,
        emp: Empleado,
        df_fichajes: pd.DataFrame,
        festivos_locales_emp: set[date],
        dias_incidencia: set[date],
        anno: int,
        mes: int,
    ) -> dict:
        festivos_nacionales = _festivos_nacionales(anno)
        festivos_totales = festivos_nacionales | festivos_locales_emp

        ultimo_dia = calendar.monthrange(anno, mes)[1]
        dias_mes = list(_daterange(date(anno, mes, 1), date(anno, mes, ultimo_dia)))

        dias_laborables = [
            d
            for d in dias_mes
            if d.weekday() < 5
            and d not in festivos_totales
            and d not in dias_incidencia
        ]
        total_laborables = len(dias_laborables)

        clave_emp        = _limpiar(emp.apellidos_y_nombre)
        clave_emp_sorted = _clave_sorted(emp.apellidos_y_nombre)

        # Primero intentar coincidencia exacta, luego order-independent
        emp_df = df_fichajes[df_fichajes["clave"] == clave_emp]
        if emp_df.empty and "clave_sorted" in df_fichajes.columns:
            emp_df = df_fichajes[df_fichajes["clave_sorted"] == clave_emp_sorted]
        validos = emp_df[emp_df["error"] == False]
        errores = emp_df[emp_df["error"] == True]

        dias_fichados = validos["Fecha"].dt.date.nunique()
        dias_error = errores["Fecha"].dt.date.nunique()
        dias_sin = total_laborables - dias_fichados - dias_error
        if dias_sin < 0:
            dias_sin = 0

        horas_reales = float(validos["horas"].sum())
        jornada = emp.jornada_semanal or 38.5
        objetivo = (jornada / 5) * total_laborables
        diferencia = horas_reales - objetivo
        horas_extra = diferencia if diferencia > 0 else 0.0

        return {
            "id": emp.id,
            "nombre": emp.apellidos_y_nombre,
            "responsable_id": emp.responsable_id or "",
            "jornada": jornada,
            "laborables": total_laborables,
            "fichados": dias_fichados,
            "errores": dias_error,
            "sin_fichar": dias_sin,
            "horas_reales": round(horas_reales, 2),
            "objetivo": round(objetivo, 2),
            "diferencia": round(diferencia, 2),
            "horas_extra": round(horas_extra, 2),
        }

    def calcular_resumen_global(
        self,
        empleados: list[Empleado],
        df_fichajes: pd.DataFrame,
        mapa_festivos: dict[str, set[date]],
        mapa_incidencias: dict[str, set[date]],
        anno: int,
        mes: int,
    ) -> list[dict]:
        resultados = []
        for emp in empleados:
            festivos_emp = mapa_festivos.get(emp.id, set())
            incidencias_emp = mapa_incidencias.get(emp.id, set())
            resumen = self.calcular_resumen_empleado(
                emp, df_fichajes, festivos_emp, incidencias_emp, anno, mes
            )
            resultados.append(resumen)
        logger.info("Resumen global calculado: %d empleados", len(resultados))
        return resultados
