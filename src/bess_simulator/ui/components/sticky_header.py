import streamlit as st


def render_sticky_header(title: str) -> None:
    st.markdown(
        f"""
        <style>
            /* Espacio para que el contenido no quede debajo del header */
            section.main .block-container {{
                padding-top: 4rem !important;
            }}
            .bess-sticky-header {{
                position: fixed;
                top: 0;
                right: 0;
                left: var(--sidebar-width, 21rem);
                background: #0e1117;
                z-index: 999;
                padding: 0.75rem 2rem;
                border-bottom: 1px solid rgba(128, 128, 128, 0.25);
                transition: left 0.3s;
            }}
            /* Cuando el sidebar está colapsado */
            [data-testid="stSidebar"][aria-expanded="false"] ~ section .bess-sticky-header {{
                left: 0;
            }}
            .bess-sticky-header h1 {{
                margin: 0;
                color: #fafafa;
                font-size: 1.8rem;
                font-weight: 700;
            }}
        </style>
        <div class="bess-sticky-header">
            <h1>{title}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ensure_view_range(bundle: dict) -> tuple:
    """Garantiza un rango de visualización por defecto en sesión y lo devuelve.

    El rango (clave ``view_range``) es **compartido** por las pantallas que lo
    aplican (vista de planta y elementos), de modo que todos los KPIs y
    variables se calculen sobre el mismo periodo. Por defecto se usa el caso de
    uso de exhibición (5 días) si cabe en el dataset; si no, los últimos 14 días
    hasta 'hoy'.
    """
    from datetime import timedelta
    from bess_simulator.engine.plant import SHOWCASE_START, SHOWCASE_END

    start_d, end_d = bundle["start"], bundle["end"]
    hoy_d = bundle.get("hoy", end_d)
    # Si la clave ya existe (aunque sea una tupla de 1 elemento mientras el
    # usuario está a mitad de seleccionar el rango) NO la sobrescribimos: hacerlo
    # reiniciaría la selección y haría imposible elegir un rango distinto.
    if "view_range" in st.session_state:
        return st.session_state["view_range"]

    show_start, show_end = SHOWCASE_START.date(), SHOWCASE_END.date()
    if start_d <= show_start and show_end <= end_d:
        default = (show_start, show_end)
    else:
        d_end = min(hoy_d, end_d)
        default = (max(start_d, d_end - timedelta(days=14)), d_end)
    st.session_state["view_range"] = default
    return default


def render_view_range(bundle: dict) -> tuple:
    """Selector de rango de visualización en la esquina superior derecha.

    Pinta el control alineado a la derecha (bajo la cabecera) usando la clave de
    sesión compartida ``view_range``. Devuelve la tupla (inicio, fin)
    seleccionada.
    """
    ensure_view_range(bundle)
    start_d, end_d = bundle["start"], bundle["end"]
    _spacer, col_range = st.columns([3, 2])
    with col_range:
        st.markdown(
            '<div style="text-align:right;color:#9aa4b2;font-size:0.78rem;'
            'margin-bottom:-0.4rem">📅 Rango de visualización</div>',
            unsafe_allow_html=True,
        )
        sel = st.date_input(
            "Rango de visualización",
            min_value=start_d, max_value=end_d,
            key="view_range",
            label_visibility="collapsed",
            help="Periodo aplicado a todos los KPIs y variables de esta vista y "
                 "de la vista de planta. No afecta a la vida útil del ROI.",
        )
    return sel
