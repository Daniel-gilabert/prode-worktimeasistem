from dataclasses import dataclass, field
from typing import Optional


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

    @classmethod
    def from_dict(cls, data: dict) -> "Empleado":
        return cls(
            id=data["id"],
            apellidos_y_nombre=data["apellidos_y_nombre"],
            email=data.get("email", ""),
            activo=data.get("activo", True),
            es_responsable=data.get("es_responsable", False),
            es_admin=data.get("es_admin", False),
            jornada_semanal=float(data.get("jornada_semanal") or 38.5),
            responsable_id=data.get("responsable_id"),
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
        }
