# PRODE WorkTimeAsistem

Coloca estos archivos en el repo `prode-worktimeasistem` y despliega en Streamlit Cloud.

## Pasos rápidos
1. Subir archivos a GitHub (app.py, requirements.txt, README.md, config_template.json, assets/logo-prode.jpg).
2. En Streamlit Cloud, conectar al repo y desplegar.
3. Crear App Registration en Azure AD (delegated permissions):
   - User.Read
   - Files.ReadWrite.All
   - Sites.ReadWrite.All
   - Configurar redirect URI según Streamlit Cloud URL y conceder admin consent.
4. En Streamlit Cloud -> Settings -> Secrets, añadir:
   - MSAL_CLIENT_ID, MSAL_TENANT_ID, MSAL_CLIENT_SECRET
   - SHAREPOINT_DRIVE_ID (opcional, puede descubrirse con Graph)
   - SHAREPOINT_ROOT_PATH (por defecto "deploy_AsistAnalyser")
   - GLOBAL_ADMIN_EMAIL (ej: danielgilabert@prode.es)
5. Desplegar y abrir la URL pública.

## Notas
- Para pruebas locales puedes dejar `LOGO_LOCAL_PATH` apuntando a `/mnt/data/logo-prode.jpg`.
- Si no configuras MSAL, la app funcionará en modo local (sin subida automática a SharePoint) — la generación de PDFs y descarga funciona localmente.
- Si configuras MSAL + Graph, la app sube los PDFs a SharePoint en la carpeta del departamento.
