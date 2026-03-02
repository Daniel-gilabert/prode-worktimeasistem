from supabase import create_client

URL = "https://gqfiarxccbaznjxispsv.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdxZmlhcnhjY2Jhem5qeGlzcHN2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjEwMjg5MiwiZXhwIjoyMDg3Njc4ODkyfQ.BdwO_YxfI3_kPRNIfKaoyyVKvLYtNaMCbsjFVmCBcxE"

sb = create_client(URL, SERVICE_KEY)
r = sb.table("panel_acceso").select("email").order("email").execute()

print(f"Registros en panel_acceso: {len(r.data)}")
for row in r.data:
    print(f"  OK  {row['email']}")
