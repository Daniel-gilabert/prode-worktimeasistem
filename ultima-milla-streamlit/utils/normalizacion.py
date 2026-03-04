def limpio(valor) -> str | None:
    """Limpia un valor de Excel: convierte nan/vacío a None."""
    if valor is None:
        return None
    s = str(valor).strip()
    return None if s in ('nan', '', 'None', 'NaN', 'NaT') else s


def n(valor) -> str | None:
    """Alias corto de limpio() para uso en formularios."""
    return limpio(valor)


def normalizar_matricula(matricula: str | None) -> str | None:
    """Elimina espacios y convierte a mayúsculas."""
    if not matricula:
        return None
    return matricula.strip().upper().replace(' ', '')


def normalizar_codigo(codigo: str | None) -> str | None:
    """Normaliza código de servicio a mayúsculas sin espacios extra."""
    if not codigo:
        return None
    return codigo.strip().upper()
