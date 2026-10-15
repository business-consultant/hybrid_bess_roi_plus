"""Internacionalización ligera de la UI (Streamlit) — español / inglés.

El idioma vive únicamente en ``st.session_state`` (no se persiste en BD):
cada sesión de navegador arranca en español y el operador puede cambiarlo
con el selector del sidebar. ``t(es, en)`` devuelve el texto en el idioma
activo; se usa como envoltura directa en los literales de cada llamada a
Streamlit/Plotly, sin tocar claves internas (dict keys, session_state,
rutas de navegación), que permanecen en español por estabilidad.
"""

from __future__ import annotations

import streamlit as st

DEFAULT_LANG = "es"
LANG_KEY = "lang"

LANGUAGES = {"es": "Español", "en": "English"}


def get_lang() -> str:
    return st.session_state.get(LANG_KEY, DEFAULT_LANG)


def set_lang(lang: str) -> None:
    st.session_state[LANG_KEY] = lang


def is_en() -> bool:
    return get_lang() == "en"


def t(es: str, en: str) -> str:
    """Devuelve ``es`` o ``en`` según el idioma activo en sesión."""
    return en if is_en() else es


def render_language_selector() -> None:
    """Selector de idioma ES/EN en el sidebar (arriba de la navegación)."""
    options = list(LANGUAGES.keys())
    current = get_lang()
    idx = options.index(current) if current in options else 0
    choice = st.sidebar.selectbox(
        "Idioma / Language",
        options=options,
        index=idx,
        format_func=lambda code: ("🇪🇸 " if code == "es" else "🇬🇧 ") + LANGUAGES[code],
        label_visibility="collapsed",
        key="lang_selector",
    )
    if choice != current:
        set_lang(choice)
        st.rerun()
