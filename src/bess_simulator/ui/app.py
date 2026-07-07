import streamlit as st

from bess_simulator.storage.paths import get_db_path, get_parquet_dir
from bess_simulator.storage.schema import init_db
from bess_simulator.storage.app_config import load_config
from bess_simulator.storage.repositories import (
    DashboardRepository,
    SensitivityRepository,
    SimulationRepository,
)

st.set_page_config(
    page_title="Bluence APM",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db(get_db_path())

if "sim_repo" not in st.session_state:
    _db = get_db_path()
    _pq = get_parquet_dir()
    st.session_state["sim_repo"] = SimulationRepository(_db, _pq)
    st.session_state["dash_repo"] = DashboardRepository(_db, _pq)
    st.session_state["sens_repo"] = SensitivityRepository(_db, _pq)
    st.session_state["app_config"] = load_config(_db)

st.markdown("""
<style>
    [data-testid='stSidebar'] .stRadio > div > label:nth-child(3) {
        margin-top: 1.2rem; padding-top: 0.8rem;
        border-top: 1px solid rgba(128,128,128,0.3);
    }
    [data-testid="stSidebarCollapseButton"] {top: 0.5rem;}
    [data-testid="stSidebarHeader"] {padding-top: 0.3rem; padding-bottom: 0; min-height: auto;}
</style>
""", unsafe_allow_html=True)

st.sidebar.markdown(
    '<div style="display:flex; align-items:baseline; gap:0.45rem; '
    'margin:0.4rem 0 1.3rem 0;">'
    '<span style="font-size:1.75rem; font-weight:800; letter-spacing:-0.02em; '
    'color:#1F4BFF; line-height:1;">Bluence</span>'
    '<span style="color:#1F4BFF; opacity:0.35; font-weight:300; '
    'font-size:1.5rem; line-height:1;">|</span>'
    '<span style="font-size:1.0rem; font-weight:600; letter-spacing:0.2em; '
    'color:#1F4BFF; line-height:1;">APM</span>'
    '</div>',
    unsafe_allow_html=True,
)

# Navegación en dos áreas: Vistas de planta (1-2) y Simulador ROI + utilidades (3-8).
# El separador visual entre ambas lo aporta el CSS (border en nth-child(3)).
page = st.sidebar.radio(
    "Navegación",
    ["Vista de planta", "Elementos de planta", "Simulador ROI",
     "Simulaciones Guardadas", "Configuración del Modelo", "Metodología", "Generación de Datos"],
    label_visibility="collapsed",
    key="nav_page",
)

if page == "Vista de planta":
    from bess_simulator.ui.views.hybrid_plant import render_hybrid_plant_page
    render_hybrid_plant_page()
elif page == "Elementos de planta":
    from bess_simulator.ui.views.monitoring import render_monitoring_page
    render_monitoring_page()
elif page == "Simulador ROI":
    from bess_simulator.ui.views.simulator import render_simulator_page
    render_simulator_page()
elif page == "Simulaciones Guardadas":
    from bess_simulator.ui.views.saved_simulations import render_saved_simulations_page
    render_saved_simulations_page()
elif page == "Configuración del Modelo":
    from bess_simulator.ui.views.settings import render_settings_page
    render_settings_page()
elif page == "Metodología":
    from bess_simulator.ui.views.methodology import render_methodology_page
    render_methodology_page()
elif page == "Generación de Datos":
    from bess_simulator.ui.views.data_generation import render_data_generation_page
    render_data_generation_page()
