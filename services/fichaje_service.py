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
    try:
        partes = str(valor).split(":")
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
        s = int(partes[2]) if len(partes) > 2 else 0
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
        df["salida_h"] = df["Hora Salida"].apply(_convertir_a_horas)
        df["error"] = df["entrada_h"] == df["salida_h"]
        df["horas"] = df["salida_h"] - df["entrada_h"]
        df.loc[df["horas"] < 0, "horas"] = 0

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
