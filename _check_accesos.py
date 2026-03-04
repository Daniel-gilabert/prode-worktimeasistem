import os, pathlib
base = pathlib.Path('.').resolve()
for n in ('.env','1.env','1.env.txt'):
    c = base / n
    if c.exists():
        for l in open(c, encoding='utf-8-sig'):
            l=l.strip()
            if not l or l.startswith('#') or '=' not in l: continue
            k,_,v=l.partition('=')
            k=k.strip(); v=v.strip().strip('"').strip("'")
            if k not in os.environ: os.environ[k]=v
        break

from supabase import create_client
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

NUEVO_DEPT = 'Reparto Ultima Milla'

depts_gls = ['Gls Córdoba', 'Gls Córdoba Pineda 3', 'Gls Jaen']

for dept in depts_gls:
    r = sb.table('empleados').update({'departamento': NUEVO_DEPT}).eq('departamento', dept).execute()
    print(f'  {dept} -> {NUEVO_DEPT}')

r2 = sb.table('empleados').select('apellidos_y_nombre,departamento').eq('departamento', NUEVO_DEPT).execute()
print(f'\nTotal en Reparto Ultima Milla ahora: {len(r2.data)}')
for e in r2.data:
    print(f'  {e["apellidos_y_nombre"]}')
