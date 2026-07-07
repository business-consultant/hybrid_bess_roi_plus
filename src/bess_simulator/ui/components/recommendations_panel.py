import streamlit as st
from bess_simulator.recommendations import FullRecommendation


# Esquema de color: el estado se usa como ACENTO (barra lateral, icono y
# etiqueta) sobre una tarjeta blanca con texto oscuro. El tono es informativo
# y agnóstico: no se desaconseja, se exponen las consecuencias para que el
# operador decida si las asume a cambio de la rentabilidad.
_STATUS_MAP = {
    "green": {
        "accent": "#1e8e3e",
        "icon": "✓",
        "label": "Rentable y seguro",
    },
    "yellow": {
        "accent": "#f29900",
        "icon": "!",
        "label": "Rentable con aspectos a vigilar",
    },
    "blue": {
        "accent": "#3b6ea5",
        "icon": "i",
        "label": "A valorar por el operador",
    },
}


def render_recommendations(rec: FullRecommendation):
    st.caption(
        "Verde = rentable y seguro · Ámbar = rentable con aspectos a vigilar · "
        "Azul = consecuencias a valorar por el operador"
    )
    status = _STATUS_MAP.get(rec.overall_color, _STATUS_MAP["yellow"])
    accent = status["accent"]

    st.markdown(
        f"""<div style="
            background:#ffffff;
            border:1px solid #e6e8eb;
            border-left:8px solid {accent};
            border-radius:10px;
            padding:20px 22px;
            margin:10px 0 14px 0;
            box-shadow:0 4px 16px rgba(15,23,42,0.10);
        ">
          <div style="display:flex; align-items:center; gap:14px;">
            <div style="
                flex:0 0 auto;
                width:42px; height:42px;
                border-radius:50%;
                background:{accent};
                color:#ffffff;
                font-size:22px; font-weight:800;
                display:flex; align-items:center; justify-content:center;
                line-height:1;
            ">{status['icon']}</div>
            <div style="flex:1 1 auto;">
              <div style="
                  font-size:0.72rem; font-weight:700; letter-spacing:0.09em;
                  text-transform:uppercase; color:#6b7280;
              ">Recomendación</div>
              <div style="font-size:1.18rem; font-weight:800; color:#111827; line-height:1.25;">
                {status['label']}
              </div>
            </div>
          </div>
          <p style="
              margin:14px 0 0 0;
              font-size:0.97rem; line-height:1.55; color:#1f2937;
          ">{rec.composite_message}</p>
        </div>""",
        unsafe_allow_html=True,
    )
