from datetime import date


def validar_rango_fechas(fecha_inicio: date, fecha_fin: date) -> str | None:
    """Devuelve mensaje de error o None si es válido."""
    if fecha_fin < fecha_inicio:
        return "La fecha de fin no puede ser anterior a la de inicio."
    return None


def validar_codigo_servicio(codigo: str) -> str | None:
    if not codigo or not codigo.strip():
        return "El código del servicio es obligatorio."
    if len(codigo.strip()) < 3:
        return "El código debe tener al menos 3 caracteres."
    return None


def validar_matricula(matricula: str) -> str | None:
    if not matricula or not matricula.strip():
        return "La matrícula es obligatoria."
    return None


def hay_solapamiento(registros: list, emp_id: int,
                     fi: date, ff: date, excluir_id: int | None = None) -> bool:
    """Comprueba si existe solapamiento de fechas para un empleado."""
    for r in registros:
        if r.get('empleado_id') != emp_id:
            continue
        if excluir_id and r.get('id') == excluir_id:
            continue
        r_fi = date.fromisoformat(str(r['fecha_inicio'])[:10])
        r_ff = date.fromisoformat(str(r['fecha_fin'])[:10])
        if fi <= r_ff and ff >= r_fi:
            return True
    return False
