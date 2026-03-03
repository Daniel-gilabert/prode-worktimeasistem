import os
from supabase import create_client

sb = create_client(
    'https://drjnffoyzuploatfcltf.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRyam5mZm95enVwbG9hdGZjbHRmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDkzMTA5MywiZXhwIjoyMDg2NTA3MDkzfQ.dJbTqUCQh6T4H2r6ThBm-CcuzSw0diiGNKsdIDFoyiY'
)

CARPETA = os.path.join(os.path.dirname(__file__), "fotos_empleados")
BUCKET  = "fotos-app"

ok = err = 0
for archivo in sorted(os.listdir(CARPETA)):
    if not archivo.lower().endswith(('.jpg', '.jpeg', '.png')):
        continue
    emp_id = os.path.splitext(archivo)[0]
    if not emp_id.isdigit():
        continue

    ruta_local = os.path.join(CARPETA, archivo)
    storage_path = f"empleados/{archivo}"

    with open(ruta_local, "rb") as f:
        contenido = f.read()

    try:
        # Subir (upsert por si ya existe)
        sb.storage.from_(BUCKET).upload(
            path=storage_path,
            file=contenido,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        url = sb.storage.from_(BUCKET).get_public_url(storage_path)

        # Actualizar foto_url en la tabla empleados
        sb.table("empleados").update({"foto_url": url}).eq("id", int(emp_id)).execute()
        print(f"  OK  ID={emp_id}  ->  {url}")
        ok += 1
    except Exception as e:
        print(f"  ERR ID={emp_id}  ->  {e}")
        err += 1

print(f"\nResultado: {ok} fotos subidas, {err} errores")
