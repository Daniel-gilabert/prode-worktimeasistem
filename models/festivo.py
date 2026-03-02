from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class FestivoLocal:
    id: str
    fecha: date
    anno: int
    descripcion: str
    responsable_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "FestivoLocal":
        fecha_val = data["fecha"]
        if isinstance(fecha_val, str):
            fecha_val = date.fromisoformat(fecha_val)
        return cls(
            id=data["id"],
            fecha=fecha_val,
            anno=data["año"],
            descripcion=data.get("descripcion") or "",
            responsable_id=data["responsable_id"],
        )


@dataclass
class FestivoEmpleado:
    id: str
    festivo_id: str
    empleado_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "FestivoEmpleado":
        return cls(
            id=data["id"],
            festivo_id=data["festivo_id"],
            empleado_id=data["empleado_id"],
        )
