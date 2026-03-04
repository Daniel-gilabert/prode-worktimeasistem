"""Tests para la lógica del semáforo."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import date, timedelta
from core.estado import calcular_estado
from core.models import Empleado, Vehiculo, Ausencia, Incidencia

HOY = date.today()
MANANA = HOY + timedelta(days=1)
AYER = HOY - timedelta(days=1)
EN_60 = HOY + timedelta(days=60)
EN_10 = HOY + timedelta(days=10)


def empleado_activo():
    return Empleado(id=1, nombre="Test", apellidos="Empleado", dni=None)

def vehiculo_ok():
    return Vehiculo(id=1, id_vehiculo="V001", matricula="TEST001", marca="Test",
                    modelo="Modelo", tipo="propiedad",
                    itv_vigente_hasta=EN_60, seguro_vigente_hasta=EN_60)

def test_operativo():
    estado = calcular_estado(1, HOY, empleado_activo(), vehiculo_ok(), [], [])
    assert estado.estado == "OPERATIVO", f"Esperado OPERATIVO, got {estado.estado}"
    print("✅ test_operativo OK")

def test_no_operativo_empleado_ausente():
    ausencia = Ausencia(id=1, empleado_id=1, fecha_inicio=AYER,
                        fecha_fin=MANANA, tipo="Vacaciones", observaciones=None)
    estado = calcular_estado(1, HOY, empleado_activo(), vehiculo_ok(), [ausencia], [])
    assert estado.estado == "NO_OPERATIVO", f"Esperado NO_OPERATIVO, got {estado.estado}"
    print("✅ test_no_operativo_empleado_ausente OK")

def test_no_operativo_itv_vencida():
    veh = vehiculo_ok()
    veh.itv_vigente_hasta = AYER
    estado = calcular_estado(1, HOY, empleado_activo(), veh, [], [])
    assert estado.estado == "NO_OPERATIVO", f"Esperado NO_OPERATIVO, got {estado.estado}"
    print("✅ test_no_operativo_itv_vencida OK")

def test_en_riesgo_itv_proxima():
    veh = vehiculo_ok()
    veh.itv_vigente_hasta = EN_10
    estado = calcular_estado(1, HOY, empleado_activo(), veh, [], [])
    assert estado.estado == "EN_RIESGO", f"Esperado EN_RIESGO, got {estado.estado}"
    print("✅ test_en_riesgo_itv_proxima OK")

if __name__ == "__main__":
    test_operativo()
    test_no_operativo_empleado_ausente()
    test_no_operativo_itv_vencida()
    test_en_riesgo_itv_proxima()
    print("\n✅ Todos los tests pasaron correctamente.")
