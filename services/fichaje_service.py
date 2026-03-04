import logging
import unicodedata
import pandas as pd
from io import BytesIO

logger = logging.getLogger(__name__)


def _limpiar(txt) -> str:
    if pd.isna(txt):
        return ""
    txt = str(txt).strip().upper()
    txt = unicodedata.normalize("NFD", txt)
    txt = txt.encode("ascii", "ignore").decode("utf-8")
    return " ".join(txt.split())


def _clave_sorted(txt) -> str:
    """Clave order-independent: palabras ordenadas alfabéticamente.
    Permite cruzar 'GILABERT CANTERO DANIEL' con 'Daniel Gilabert Cantero'."""
    return " ".join(sorted(_limpiar(txt).split()))


def _convertir_a_horas(valor) -> float | None:
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass
    # datetime.time o pd.Timestamp — tienen atributo .hour
    if hasattr(valor, "hour"):
        return valor.hour + valor.minute / 60 + getattr(valor, "second", 0) / 3600
    # timedelta — duracion directa
    if hasattr(valor, "total_seconds"):
        return valor.total_seconds() / 3600
    # string — varios formatos posibles
    try:
        txt = str(valor).strip()
        if " " in txt:
            txt = txt.split(" ")[-1]   # "1900-01-01 09:03:44" -> "09:03:44"
        partes = txt.split(":")
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
        s = int(float(partes[2])) if len(partes) > 2 else 0
        return h + m / 60 + s / 3600
    except Exception:
        return None


class FichajeService:
    def cargar_fichajes(self, file) -> pd.DataFrame:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()

        df = df[
            ~df.iloc[:, 0]
            .astype(str)
            .str.upper()
            .str.startswith("FILTROS APLICADOS", na=False)
        ]
        df = df[
            ~df.iloc[:, 0].astype(str).str.upper().str.contains("TOTAL", na=False)
        ]

        df["clave"]        = df["Apellidos y Nombre"].apply(_limpiar)
        df["clave_sorted"] = df["Apellidos y Nombre"].apply(_clave_sorted)
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        df["entrada_h"] = df["Hora Entrada"].apply(_convertir_a_horas)
        df["salida_h"]  = df["Hora Salida"].apply(_convertir_a_horas)

        # error = ambos válidos Y iguales (entrada=salida -> tiempo trabajado = 0)
        # NaN != NaN en pandas, así que usamos comparación explícita
        def _es_error(row) -> bool:
            e, s = row["entrada_h"], row["salida_h"]
            if e is None or s is None:
                return True   # sin datos = error
            if pd.isna(e) or pd.isna(s):
                return True
            return abs(e - s) < 0.001  # misma hora con margen de 3.6 seg

        df["error"] = df.apply(_es_error, axis=1)

        # Usar "Tiempo trabajado" si existe y tiene valor válido > 0
        # Si no (columna ausente, cero o errónea), calcular con Salida − Entrada
        if "Tiempo trabajado" in df.columns:
            df["tiempo_trabajado_h"] = df["Tiempo trabajado"].apply(_convertir_a_horas)
            usar_tiempo_trabajado = (
                df["tiempo_trabajado_h"].notna() & (df["tiempo_trabajado_h"] > 0)
            )
            df["horas"] = 0.0
            df.loc[usar_tiempo_trabajado, "horas"] = df.loc[usar_tiempo_trabajado, "tiempo_trabajado_h"]
            df.loc[~usar_tiempo_trabajado, "horas"] = (
                (df.loc[~usar_tiempo_trabajado, "salida_h"] - df.loc[~usar_tiempo_trabajado, "entrada_h"])
                .clip(lower=0)
            )
        else:
            df["horas"] = (df["salida_h"] - df["entrada_h"]).clip(lower=0)

        df.loc[df["error"], "horas"] = 0.0

        logger.info(
            "Fichajes cargados: %d registros, %d empleados únicos",
            len(df),
            df["clave"].nunique(),
        )
        return df

    def detectar_periodo(self, df: pd.DataFrame) -> tuple[int, int]:
        anno = int(df["Fecha"].dt.year.mode()[0])
        mes = int(df["Fecha"].dt.month.mode()[0])
        logger.debug("Periodo detectado: %d/%d", mes, anno)
        return anno, mes

    def clave_empleado(self, nombre: str) -> str:
        return _limpiar(nombre)

    def clave_sorted(self, nombre: str) -> str:
        return _clave_sorted(nombre)
