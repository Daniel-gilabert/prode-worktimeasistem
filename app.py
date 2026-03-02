import os
import logging
import logging.handlers
import pathlib
import streamlit as st

def _cargar_env() -> None:
    base = pathlib.Path(__file__).resolve().parent
    for nombre in (".env", "1.env", "1.env.txt"):
        candidato = base / nombre
        if candidato.exists():
            with open(candidato, encoding="utf-8-sig") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#") or "=" not in linea:
                        continue
                    clave, _, valor = linea.partition("=")
                    clave = clave.strip()
                    valor = valor.strip().strip('"').strip("'")
                    if clave and clave not in os.environ:
                        os.environ[clave] = valor
            return

_cargar_env()

# =============================================================================
# LOGGING
# =============================================================================

def _configurar_logging() -> None:
    os.makedirs("logs", exist_ok=True)
    nivel = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.setLevel(nivel)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

_configurar_logging()
logger = logging.getLogger(__name__)

# =============================================================================
# GUARDIA DE SEGURIDAD
# =============================================================================

if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
    st.set_page_config(page_title="WorkTimeAsistem PRODE", layout="centered")
    st.error(
        "Faltan las variables de entorno SUPABASE_URL y SUPABASE_KEY. "
        "Crea el archivo .env con las credenciales correctas."
    )
    logger.critical("Arranque abortado: SUPABASE_URL o SUPABASE_KEY no definidos.")
    st.stop()

# =============================================================================
# IMPORTS
# =============================================================================

from repositories.empleado_repo import EmpleadoRepository
from repositories.festivo_repo import FestivoRepository
from repositories.incidencia_repo import IncidenciaRepository
from repositories.panel_acceso_repo import PanelAccesoRepository
from repositories.historico_repo import HistoricoRepository
from services.fichaje_service import FichajeService
from services.calculo_service import CalculoService
from ui.login import render_login
from ui.configuracion import render_configuracion
from ui.resumen import render_resumen
from ui.exportacion import render_exportacion
from ui.panel_responsables import render_panel_responsables
from ui.historico import render_historico

# =============================================================================
# CONFIGURACIÓN DE PÁGINA
# =============================================================================

st.set_page_config(
    page_title="WorkTimeAsistem PRODE",
    page_icon="assets/logo-prode.png" if os.path.exists("assets/logo-prode.png") else None,
    layout="wide",
)

LOGO_PATH = "assets/logo-prode.png" if os.path.exists("assets/logo-prode.png") else None

# =============================================================================
# LOGIN
# =============================================================================

if not render_login():
    st.stop()

usuario = st.session_state["usuario"]

# =============================================================================
# BARRA LATERAL
# =============================================================================

with st.sidebar:
    if LOGO_PATH:
        st.image(LOGO_PATH, width=160)
    st.markdown(f"**{usuario.apellidos_y_nombre}**")
    rol_texto = "Administrador" if usuario.es_admin else "Responsable"
    st.caption(rol_texto)
    st.divider()
    if st.button("Cerrar sesión", use_container_width=True):
        logger.info("Cierre de sesión: %s", usuario.email)
        st.session_state.clear()
        st.rerun()

# =============================================================================
# ENRUTAMIENTO: panel user vs usuario normal
# =============================================================================

acceso_repo   = PanelAccesoRepository()
es_panel_user = acceso_repo.tiene_acceso(usuario.email)

emp_repo  = EmpleadoRepository()
fest_repo = FestivoRepository()
inc_repo  = IncidenciaRepository()

# =============================================================================
# FLUJO A — USUARIO DE PANEL (solo panel, sin config ni resumen detallado)
# =============================================================================

if es_panel_user:

    st.divider()
    col_up_a, col_graf_a = st.columns([4, 2])
    with col_up_a:
        uploaded = st.file_uploader(
            "Sube el Excel mensual de fichajes",
            type=["xlsx"],
            key="upload_excel",
            help="Exportado directamente desde el sistema de control de presencia.",
        )
    with col_graf_a:
        st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<a href='#historico-evolucion' style='display:block;text-align:center;"
            "background:#1a3d6e;color:white;padding:8px 12px;border-radius:6px;"
            "text-decoration:none;font-size:14px;'>Ver gráficas de evolución ↓</a>",
            unsafe_allow_html=True,
        )

    if not uploaded:
        st.info("Sube el Excel de fichajes para comenzar el análisis.")
        st.stop()

    fichaje_svc = FichajeService()
    calc_svc    = CalculoService()

    try:
        df_fichajes = fichaje_svc.cargar_fichajes(uploaded)
        anno, mes   = fichaje_svc.detectar_periodo(df_fichajes)
    except Exception as e:
        logger.exception("Error al procesar el Excel (panel user)")
        st.error(f"Error al leer el archivo: {e}")
        st.stop()

    todos_empleados  = emp_repo.get_todos_activos()
    mapa_festivos    = fest_repo.get_todos_festivos_por_empleado(anno)
    mapa_incidencias = inc_repo.get_dias_por_empleado()

    resumen_global = calc_svc.calcular_resumen_global(
        todos_empleados, df_fichajes, mapa_festivos, mapa_incidencias, anno, mes
    )

    render_panel_responsables(usuario, todos_empleados, resumen_global, mes, anno)
    render_historico(usuario, resumen_global, anno, mes, mostrar_todos=True)
    st.stop()

# =============================================================================
# FLUJO B — USUARIO NORMAL (configuración + resumen + exportación)
# =============================================================================

st.divider()

col_up, col_graf = st.columns([4, 2])
with col_up:
    uploaded = st.file_uploader(
        "Sube el Excel mensual de fichajes",
        type=["xlsx"],
        key="upload_excel",
        help="Exportado directamente desde el sistema de control de presencia.",
    )
with col_graf:
    st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<a href='#historico-evolucion' style='display:block;text-align:center;"
        "background:#1a3d6e;color:white;padding:8px 12px;border-radius:6px;"
        "text-decoration:none;font-size:14px;'>Ver gráficas de evolución ↓</a>",
        unsafe_allow_html=True,
    )

if not uploaded:
    st.info("Sube el Excel de fichajes para comenzar el análisis.")
    st.stop()

fichaje_svc = FichajeService()

try:
    df_fichajes = fichaje_svc.cargar_fichajes(uploaded)
    anno, mes   = fichaje_svc.detectar_periodo(df_fichajes)
except Exception as e:
    logger.exception("Error al procesar el Excel de fichajes")
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

empleados        = emp_repo.get_activos(usuario)
todos_empleados  = emp_repo.get_todos_activos()

if not empleados:
    st.warning("No se encontraron empleados activos asignados a tu cuenta.")
    st.stop()

mapa_festivos    = fest_repo.get_festivos_por_empleado(anno, usuario.id)
mapa_incidencias = inc_repo.get_dias_por_empleado()

render_configuracion(usuario, empleados, anno)
resumen = render_resumen(empleados, df_fichajes, mapa_festivos, mapa_incidencias, anno, mes)
render_exportacion(resumen, mes, anno, logo_path=LOGO_PATH)
render_historico(usuario, resumen, anno, mes, mostrar_todos=False)
