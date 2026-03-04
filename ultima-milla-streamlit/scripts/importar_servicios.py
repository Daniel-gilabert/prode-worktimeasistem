"""
Importa servicios desde la plantilla Excel rellena.
Uso: python importar_servicios.py PLANTILLA_SERVICIOS.xlsx
"""
import sys
import pandas as pd
from datetime import date
from supabase import create_client

SUPABASE_URL = 'https://drjnffoyzuploatfcltf.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRyam5mZm95enVwbG9hdGZjbHRmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDkzMTA5MywiZXhwIjoyMDg2NTA3MDkzfQ.dJbTqUCQh6T4H2r6ThBm-CcuzSw0diiGNKsdIDFoyiY'

archivo = sys.argv[1] if len(sys.argv) > 1 else 'PLANTILLA_SERVICIOS.xlsx'
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def limpio(val):
    s = str(val).strip()
    return None if s in ('nan', '', 'None') else s

def a_fecha(val):
    if val is None or str(val).strip() in ('nan', '', 'None'):
        return None
    try:
        if isinstance(val, (date,)):
            return str(val)
        return pd.to_datetime(val, dayfirst=True).strftime('%Y-%m-%d')
    except Exception:
        return None

def a_decimal(val):
    try:
        return float(str(val).replace(',', '.').replace('€', '').strip())
    except Exception:
        return None

# ── Cargar empleados y vehículos ─────────────────────────────
emp_sb = sb.table('empleados').select('id, nombre, apellidos').execute().data
veh_sb = sb.table('vehiculos').select('id, matricula, marca, modelo').execute().data

emp_idx = {f"{e['apellidos'].upper()}, {e['nombre'].upper()}": e['id'] for e in emp_sb}
veh_idx = {v['matricula'].strip().upper(): v['id'] for v in veh_sb}

# ── Leer Excel ────────────────────────────────────────────────
df = pd.read_excel(archivo, sheet_name='Servicios', header=1, skiprows=[2])
df = df.fillna('')
df.columns = [str(c).strip() for c in df.columns]

print(f"Filas en Excel: {len(df)}")

ok, errores = 0, []
for i, row in df.iterrows():
    codigo = limpio(row.get('CODIGO_SERVICIO'))
    if not codigo:
        continue

    # Resolver empleado
    emp_raw = limpio(row.get('EMPLEADO_BASE', ''))
    emp_id  = None
    if emp_raw:
        emp_id = emp_idx.get(emp_raw.upper())
        if not emp_id:
            # Buscar por apellidos
            partes = emp_raw.upper().split(',')
            for k, v in emp_idx.items():
                if partes[0].strip() in k:
                    emp_id = v
                    break

    # Resolver vehículo
    veh_raw = limpio(row.get('VEHICULO_BASE', ''))
    veh_id  = None
    if veh_raw:
        matricula = veh_raw.split('-')[0].strip().upper()
        veh_id    = veh_idx.get(matricula)

    if not emp_id or not veh_id:
        errores.append(f"Fila {i+4} [{codigo}]: empleado={emp_raw} vehículo={veh_raw}")
        continue

    registro = {
        'codigo':                codigo,
        'descripcion':           limpio(row.get('DESCRIPCION')) or codigo,
        'zona':                  limpio(row.get('ZONA_LOCALIDAD')),
        'tipo_servicio':         limpio(row.get('TIPO_SERVICIO')),
        'fecha_inicio_contrato': a_fecha(row.get('FECHA_INICIO_CONTRATO')),
        'fecha_fin_contrato':    a_fecha(row.get('FECHA_FIN_CONTRATO')),
        'dias_servicio':         limpio(row.get('DIAS_SERVICIO')),
        'horario_inicio':        limpio(row.get('HORARIO_INICIO')),
        'horario_fin':           limpio(row.get('HORARIO_FIN')),
        'empleado_base_id':      emp_id,
        'vehiculo_base_id':      veh_id,
        'empresa_nombre':        limpio(row.get('EMPRESA_NOMBRE')),
        'empresa_cif':           limpio(row.get('EMPRESA_CIF')),
        'empresa_direccion':     limpio(row.get('EMPRESA_DIRECCION')),
        'empresa_cp':            limpio(row.get('EMPRESA_CP')),
        'empresa_ciudad':        limpio(row.get('EMPRESA_CIUDAD')),
        'empresa_provincia':     limpio(row.get('EMPRESA_PROVINCIA')),
        'empresa_pais':          limpio(row.get('EMPRESA_PAIS')) or 'España',
        'contacto_nombre':       limpio(row.get('CONTACTO_NOMBRE')),
        'contacto_cargo':        limpio(row.get('CONTACTO_CARGO')),
        'contacto_email':        limpio(row.get('CONTACTO_EMAIL')),
        'contacto_telefono':     limpio(row.get('CONTACTO_TELEFONO')),
        'contacto_movil':        limpio(row.get('CONTACTO_MOVIL')),
        'contacto2_nombre':      limpio(row.get('CONTACTO2_NOMBRE')),
        'contacto2_email':       limpio(row.get('CONTACTO2_EMAIL')),
        'contacto2_telefono':    limpio(row.get('CONTACTO2_TELEFONO')),
        'facturacion_email':     limpio(row.get('FACTURACION_EMAIL')),
        'facturacion_forma_pago':limpio(row.get('FACTURACION_FORMA_PAGO')),
        'tarifa_mensual':        a_decimal(row.get('TARIFA_MENSUAL')),
        'observaciones':         limpio(row.get('OBSERVACIONES')),
        'activo':                True,
    }
    # Limpiar Nones
    registro = {k: v for k, v in registro.items() if v is not None}

    try:
        # Upsert por código (actualiza si ya existe)
        sb.table('servicios').upsert(registro, on_conflict='codigo').execute()
        ok += 1
        print(f"OK: {codigo} — {registro.get('descripcion','')}")
    except Exception as e:
        errores.append(f"Fila {i+4} [{codigo}]: {e}")

print(f"\n{'='*50}")
print(f"IMPORTADOS: {ok}")
if errores:
    print(f"ERRORES ({len(errores)}):")
    for e in errores:
        print(f"  ✗ {e}")
else:
    print("Sin errores.")
