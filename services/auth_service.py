import logging
from enum import Enum
from typing import Optional
from models.empleado import Empleado
from repositories.empleado_repo import EmpleadoRepository

logger = logging.getLogger(__name__)


class Rol(str, Enum):
    ADMIN = "admin"
    RESPONSABLE = "responsable"


class AuthService:
    def __init__(self):
        self._repo = EmpleadoRepository()

    def login(self, email: str) -> Optional[Empleado]:
        email = email.strip().lower()
        empleado = self._repo.get_by_email(email)
        if empleado and (empleado.es_responsable or empleado.es_admin):
            logger.info("Login exitoso: %s (admin=%s)", email, empleado.es_admin)
            return empleado
        logger.warning("Login fallido para: %s", email)
        return None

    def verificar_rol(self, usuario: Empleado, rol: Rol) -> bool:
        if rol == Rol.ADMIN:
            return usuario.es_admin
        if rol == Rol.RESPONSABLE:
            return usuario.es_responsable or usuario.es_admin
        return False

    def es_admin(self, usuario: Empleado) -> bool:
        return usuario.es_admin

    def puede_ver_empleado(self, usuario: Empleado, empleado: Empleado) -> bool:
        if usuario.es_admin:
            return True
        return empleado.responsable_id == usuario.id
