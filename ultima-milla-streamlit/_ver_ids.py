from supabase import create_client
sb = create_client(
    'https://drjnffoyzuploatfcltf.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRyam5mZm95enVwbG9hdGZjbHRmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDkzMTA5MywiZXhwIjoyMDg2NTA3MDkzfQ.dJbTqUCQh6T4H2r6ThBm-CcuzSw0diiGNKsdIDFoyiY'
)
res = sb.table('servicios').select('codigo,descripcion,empresa_nombre,empresa_cif,contacto_nombre,contacto_email,contacto_telefono,facturacion_forma_pago,numero_cuenta,empleado_base_id,vehiculo_base_id,dimension').order('codigo').execute()
print(f"Total servicios en Supabase: {len(res.data)}\n")
for s in res.data:
    print(f"  {s['codigo']} | {s['descripcion']} | empresa={s.get('empresa_nombre','')} | emp_id={s.get('empleado_base_id','')} | veh_id={s.get('vehiculo_base_id','')}")
