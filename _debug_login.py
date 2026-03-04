import os, pathlib

base = pathlib.Path(".").resolve()
for n in (".env", "1.env", "1.env.txt"):
    c = base / n
    if c.exists():
        for l in c.read_text(encoding="utf-8-sig").splitlines():
            l = l.strip()
            if not l or l.startswith("#") or "=" not in l:
                continue
            k, _, v = l.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

from supabase import create_client
cl = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

email = "danielgilabert@prode.es"

print(f"SUPABASE_URL  = {os.environ['SUPABASE_URL']}")
key = os.environ["SUPABASE_KEY"]
# Decodifica el payload del JWT para ver el rol
import base64, json
payload = key.split(".")[1]
payload += "=" * (4 - len(payload) % 4)
decoded = json.loads(base64.b64decode(payload))
print(f"KEY role      = {decoded.get('role')}  (debe ser service_role)")
print()

# Busca el empleado directamente
r = cl.table("empleados").select("*").eq("email", email).execute()
print(f"Filas encontradas para '{email}': {len(r.data)}")
for row in r.data:
    print(f"  activo={row['activo']}  es_responsable={row['es_responsable']}  es_admin={row['es_admin']}")

print()
# Prueba exactamente lo que hace auth_service
email_norm = email.strip().lower()
print(f"Email normalizado: '{email_norm}'")
print(f"Termina en @prode.es: {email_norm.endswith('@prode.es')}")
