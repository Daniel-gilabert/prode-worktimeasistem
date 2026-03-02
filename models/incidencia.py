from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class TipoIncidencia(str, Enum):
    VACACIONES = "VACACIONES"
    BAJA = "BAJA"
    PERMISO = "PERMISO"


@dataclass
class Incidencia:
    id: str
    empleado_id: str
    tipo: TipoIncidencia
    fecha_inicio: date
    fecha_fin: date
    descripcion: str
    created_by: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Incidencia":
        fi = data["fecha_inicio"]
        ff = data["fecha_fin"]
        if isinstance(fi, str):
            fi = date.fromisoformat(fi[:10])
        if isinstance(ff, str):
            ff = date.fromisoformat(ff[:10])
        return cls(
            id=data["id"],
            empleado_id=data["empleado_id"],
            tipo=TipoIncidencia(data["tipo"]),
            fecha_inicio=fi,
            fecha_fin=ff,
            descripcion=data.get("descripcion") or "",
            created_by=data.get("created_by"),
        )
