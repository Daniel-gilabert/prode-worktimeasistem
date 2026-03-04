from datetime import date, datetime


def a_fecha(valor) -> str | None:
    """Convierte cualquier valor a string YYYY-MM-DD o None."""
    if valor is None:
        return None
    s = str(valor).strip()
    if s in ('', 'nan', 'None', 'NaT'):
        return None
    try:
        if isinstance(valor, (date, datetime)):
            return valor.strftime('%Y-%m-%d')
        import pandas as pd
        return pd.to_datetime(valor, dayfirst=True).strftime('%Y-%m-%d')
    except Exception:
        return None


def dias_hasta(fecha_str: str | None, desde: date | None = None) -> int | None:
    """Días que faltan hasta una fecha. Negativo = ya vencida."""
    if not fecha_str:
        return None
    try:
        destino = date.fromisoformat(str(fecha_str)[:10])
        origen  = desde or date.today()
        return (destino - origen).days
    except Exception:
        return None


def formatear_fecha(fecha_str: str | None, formato: str = '%d/%m/%Y') -> str:
    """Devuelve fecha legible o '—' si es None."""
    if not fecha_str:
        return '—'
    try:
        return date.fromisoformat(str(fecha_str)[:10]).strftime(formato)
    except Exception:
        return str(fecha_str)
