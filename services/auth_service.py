import logging
from enum import Enum
from typing import Optional
from models.empleado import Empleado
from repositories.empleado_repo import EmpleadoRepository
from repositories.panel_acceso_repo import PanelAccesoRepository
from repositories import auditoria_repo

logger = logging.getLogger(__name__)

DOMINIO_PERMITIDO = "prode.es"


class Rol(str, Enum):
    ADMIN = "admin"
    RESPONSABLE = "responsable"


class AuthService:
    def __init__(self):
        self._repo       = EmpleadoRepository()
        self._panel_repo = PanelAccesoRepository()

    def login(self, email: str) -> Optional[Empleado]:
        email = email.strip().lower()

        # 1 — Solo dominio corporativo
        if not email.endswith(f"@{DOMINIO_PERMITIDO}"):
            logger.warning("Login bloqueado — dominio no permitido: %s", email)
            auditoria_repo.registrar(email, "LOGIN", "Dominio no permitido", "bloqueado")
            return None

        # 2 — Debe estar en la tabla empleados con rol activo
        empleado = self._repo.get_by_email(email)
        if not empleado:
            # Comprueba si al menos está en panel_acceso (usuario de panel sin ficha)
            if self._panel_repo.tiene_acceso(email):
                logger.warning("Panel user sin ficha en empleados: %s", email)
                auditoria_repo.registrar(email, "LOGIN", "En panel_acceso pero sin registro en empleados", "denegado")
            else:
                logger.warning("Login denegado — correo no registrado: %s", email)
                auditoria_repo.registrar(email, "LOGIN", "Correo no registrado en la base de datos", "denegado")
            return None

        # 3 — Debe tener rol asignado (responsable o admin)
        if not (empleado.es_responsable or empleado.es_admin):
            logger.warning("Login denegado — sin rol asignado: %s", email)
            auditoria_repo.registrar(email, "LOGIN", "Sin rol de responsable ni admin asignado", "denegado")
            return None

        # 4 — Acceso concedido
        logger.info("Login exitoso: %s (admin=%s)", email, empleado.es_admin)
        auditoria_repo.registrar(email, "LOGIN", f"admin={empleado.es_admin}", "ok")
        return empleado

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
