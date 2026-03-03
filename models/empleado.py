from dataclasses import dataclass
from typing import Optional

ROLES_VALIDOS = ("empleado", "coordinador", "responsable", "administrador", "superadministrador")
SUPERADMIN_EMAIL = "danielgilabert@prode.es"


@dataclass
class Empleado:
    id: str
    apellidos_y_nombre: str
    email: str
    activo: bool = True
    es_responsable: bool = False
    es_admin: bool = False
    jornada_semanal: float = 38.5
    responsable_id: Optional[str] = None
    rol: str = "empleado"
    departamento: str = ""

    # ── helpers de rol ───────────────────────────────────────────
    @property
    def es_superadmin(self) -> bool:
        return self.email.strip().lower() == SUPERADMIN_EMAIL

    @property
    def tiene_acceso_app(self) -> bool:
        return self.rol in ("coordinador", "responsable", "administrador", "superadministrador")

    @property
    def vista(self) -> str:
        """Vista que ve en la app."""
        if self.es_superadmin or self.rol == "administrador":
            return "administrador"
        if self.rol in ("responsable", "coordinador"):
            return "responsable"
        return "ninguna"

    @classmethod
    def from_dict(cls, data: dict) -> "Empleado":
        rol_raw = (data.get("rol") or "").strip().lower()
        # Derivar rol desde campos legados si no existe
        if not rol_raw or rol_raw not in ROLES_VALIDOS:
            if data.get("es_admin"):
                rol_raw = "administrador"
            elif data.get("es_responsable"):
                rol_raw = "responsable"
            else:
                rol_raw = "empleado"
        return cls(
            id=data["id"],
            apellidos_y_nombre=data["apellidos_y_nombre"],
            email=data.get("email", ""),
            activo=data.get("activo", True),
            es_responsable=rol_raw in ("responsable", "coordinador"),
            es_admin=rol_raw in ("administrador", "superadministrador"),
            jornada_semanal=float(data.get("jornada_semanal") or 38.5),
            responsable_id=data.get("responsable_id"),
            rol=rol_raw,
            departamento=(data.get("departamento") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "apellidos_y_nombre": self.apellidos_y_nombre,
            "email": self.email,
            "activo": self.activo,
            "es_responsable": self.es_responsable,
            "es_admin": self.es_admin,
            "jornada_semanal": self.jornada_semanal,
            "responsable_id": self.responsable_id,
            "rol": self.rol,
            "departamento": self.departamento,
        }
