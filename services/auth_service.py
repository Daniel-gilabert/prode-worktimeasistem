import logging
from typing import Optional
from models.empleado import Empleado, SUPERADMIN_EMAIL
from repositories.empleado_repo import EmpleadoRepository
from repositories import auditoria_repo

logger = logging.getLogger(__name__)
DOMINIO_PERMITIDO = "prode.es"


class AuthService:
    def __init__(self):
        self._repo = EmpleadoRepository()

    def login(self, email: str) -> Optional[Empleado]:
        email = email.strip().lower()

        if not email.endswith(f"@{DOMINIO_PERMITIDO}"):
            logger.warning("Login bloqueado — dominio no permitido: %s", email)
            auditoria_repo.registrar(email, "LOGIN", "Dominio no permitido", "bloqueado")
            return None

        empleado = self._repo.get_by_email(email)
        if not empleado:
            logger.warning("Login denegado — correo no registrado: %s", email)
            auditoria_repo.registrar(email, "LOGIN", "Correo no registrado", "denegado")
            return None

        if not empleado.tiene_acceso_app and not empleado.es_superadmin:
            logger.warning("Login denegado — sin acceso: %s (rol=%s)", email, empleado.rol)
            auditoria_repo.registrar(email, "LOGIN", f"Sin acceso — rol={empleado.rol}", "denegado")
            return None

        logger.info("Login exitoso: %s (rol=%s)", email, empleado.rol)
        auditoria_repo.registrar(email, "LOGIN", f"rol={empleado.rol} dept={empleado.departamento}", "ok")
        return empleado

    def es_superadmin(self, usuario: Empleado) -> bool:
        return usuario.es_superadmin

    def es_admin_o_superior(self, usuario: Empleado) -> bool:
        return usuario.vista == "administrador"

    def puede_ver_empleado(self, usuario: Empleado, empleado: Empleado) -> bool:
        if usuario.vista == "administrador":
            return True
        if usuario.departamento:
            return empleado.departamento == usuario.departamento
        return empleado.responsable_id == usuario.id
