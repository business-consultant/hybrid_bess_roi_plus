"""Panel de registro de eventos críticos (APM).

Renderiza, a partir del histórico, las anomalías de magnitudes críticas
(seguridad, salud y garantía) detectadas por
:func:`bess_simulator.recommendations.alarms.check_historical_alarms`.

Cada evento se muestra como una tarjeta con su severidad, categoría, alcance
temporal y el subsistema responsable. El campo ``subelement`` está pensado para
que más adelante la tarjeta enlace (atajo) con la pantalla de detalle por
elemento.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bess_simulator.i18n import get_lang, t
from bess_simulator.recommendations.alarms import (
    Alarm,
    SEVERITY_CRITICAL,
    check_historical_alarms,
)

# Los valores internos (category/severity/subelement) permanecen en español:
# son los que produce el motor de alarmas y se usan como claves en varios
# diccionarios. Solo se traduce la ETIQUETA mostrada en pantalla.
_SEVERITY_STYLE = {
    SEVERITY_CRITICAL: {"accent": "#d23f31", "icon": "⛔", "label_es": "Crítico", "label_en": "Critical"},
    "warning": {"accent": "#f29900", "icon": "⚠️", "label_es": "Aviso", "label_en": "Warning"},
}

_CATEGORY_ICON = {
    "Seguridad": "🛡️",
    "Salud del activo": "🩺",
    "Garantía contractual": "📋",
}

_CATEGORY_LABEL_EN = {
    "Seguridad": "Safety",
    "Salud del activo": "Asset health",
    "Garantía contractual": "Contractual warranty",
}

# Atajo: subsistema responsable de la alarma → elemento de la pantalla de detalle.
_SUBELEMENT_TO_ELEMENT = {
    "Sistema térmico / HVAC": "HVAC",
    "PCS / Inversor BESS": "PCS",
    "Módulos BESS": "Módulos BESS",
}

_ELEMENT_LABEL_EN = {
    "HVAC": "HVAC",
    "PCS": "PCS",
    "Módulos BESS": "BESS modules",
}


def _goto_element(element_name: str) -> None:
    """Atajo: navega a 'Elementos de planta' y abre el detalle del elemento."""
    st.session_state["nav_page"] = "Elementos de planta"
    st.session_state["monitoring_element"] = element_name


def _goto_plant_range(first: pd.Timestamp | None, last: pd.Timestamp | None) -> None:
    """Atajo: navega a 'Vista de planta' y encuadra el rango en los eventos.

    Ajusta el rango de visualización compartido (``view_range``) para que cubra
    la ventana en la que sucedieron los eventos críticos, de modo que el registro
    (que vive al final de la vista de planta) sea coherente con lo seleccionado.
    """
    st.session_state["nav_page"] = "Vista de planta"
    if first is not None and last is not None:
        st.session_state["view_range"] = (
            pd.Timestamp(first).date(),
            pd.Timestamp(last).date(),
        )



def _fmt_period(first: pd.Timestamp | None, last: pd.Timestamp | None) -> str:
    if first is None:
        return "—"
    if last is None or pd.Timestamp(first).date() == pd.Timestamp(last).date():
        return pd.Timestamp(first).strftime("%d/%m/%Y")
    return (
        f"{pd.Timestamp(first).strftime('%d/%m/%Y')} → "
        f"{pd.Timestamp(last).strftime('%d/%m/%Y')}"
    )


def _element_label(element: str) -> str:
    return t(element, _ELEMENT_LABEL_EN.get(element, element))


def _render_event_card(alarm: Alarm, idx: int = 0) -> None:
    style = _SEVERITY_STYLE.get(alarm.severity, _SEVERITY_STYLE["warning"])
    severity_label = t(style["label_es"], style["label_en"])
    cat_icon = _CATEGORY_ICON.get(alarm.category, "•")
    cat_label = t(alarm.category, _CATEGORY_LABEL_EN.get(alarm.category, alarm.category))
    period = _fmt_period(alarm.first_timestamp, alarm.last_timestamp)
    st.markdown(
        f"""
        <div style="background:#ffffff;border:1px solid #e5e7eb;
             border-left:6px solid {style['accent']};border-radius:10px;
             padding:0.75rem 1rem;margin-bottom:0.6rem;
             box-shadow:0 2px 8px rgba(0,0,0,0.05)">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:700;color:#1f2937">
              {style['icon']} {alarm.parameter}
              <span style="font-size:0.72rem;color:#6c757d;font-weight:600;
                   margin-left:6px">{cat_icon} {cat_label}</span>
            </span>
            <span style="font-size:0.72rem;font-weight:700;color:{style['accent']};
                 text-transform:uppercase;letter-spacing:0.05em">{severity_label}</span>
          </div>
          <div style="color:#374151;font-size:0.9rem;margin-top:4px">{alarm.message}.</div>
          <div style="color:#6c757d;font-size:0.76rem;margin-top:6px">
            📅 {period} &nbsp;·&nbsp; 🔧 {alarm.subelement}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    element = _SUBELEMENT_TO_ELEMENT.get(alarm.subelement)
    if element:
        st.button(
            t(f"🔧 Ver detalle de {element} →", f"🔧 View {_element_label(element)} detail →"),
            key=f"alert_shortcut_{idx}",
            on_click=_goto_element, args=(element,),
        )


def render_alerts_panel(df: pd.DataFrame, cfg: dict | None = None) -> None:
    """Dibuja el registro de eventos críticos del histórico."""
    if df is None or df.empty:
        return

    hist = df[~df["is_forecast"]] if "is_forecast" in df.columns else df
    alarms = check_historical_alarms(hist, cfg=cfg, lang=get_lang())

    n_crit = sum(1 for a in alarms if a.severity == SEVERITY_CRITICAL)
    badge = ""
    if alarms:
        badge = t(f" · {len(alarms)} evento(s)", f" · {len(alarms)} event(s)")
        if n_crit:
            badge += t(f", {n_crit} crítico(s)", f", {n_crit} critical")

    st.markdown(f"### 🔔 {t('Registro de eventos críticos', 'Critical events log')}{badge}")
    st.caption(
        t(
            "Magnitudes críticas (seguridad, salud y garantía contractual) que han "
            "operado fuera de rango en el histórico.",
            "Critical magnitudes (safety, health and contractual warranty) that have "
            "operated out of range in the historical data.",
        )
    )

    if not alarms:
        st.success(
            t(
                "Sin eventos críticos registrados: todas las magnitudes vigiladas se "
                "han mantenido dentro de los rangos admisibles.",
                "No critical events recorded: all monitored magnitudes have stayed "
                "within admissible ranges.",
            )
        )
        return

    # Críticos primero.
    for idx, alarm in enumerate(sorted(alarms, key=lambda a: a.severity != SEVERITY_CRITICAL)):
        _render_event_card(alarm, idx)


def render_critical_events_shortcut(df: pd.DataFrame, cfg: dict | None = None) -> None:
    """Menciona los eventos críticos del histórico y ofrece accesos directos.

    Pensado para el simulador ROI: avisa de que la operación histórica del activo
    registró eventos críticos y enlaza tanto con el registro completo (Vista de
    planta) como con el detalle del subelemento responsable. El rango de la vista
    de planta se encuadra automáticamente en la ventana de los eventos.
    """
    if df is None or df.empty:
        return

    hist = df[~df["is_forecast"]] if "is_forecast" in df.columns else df
    alarms = check_historical_alarms(hist, cfg=cfg, lang=get_lang())
    if not alarms:
        return

    n_crit = sum(1 for a in alarms if a.severity == SEVERITY_CRITICAL)
    firsts = [a.first_timestamp for a in alarms if a.first_timestamp is not None]
    lasts = [a.last_timestamp for a in alarms if a.last_timestamp is not None]
    first = min(firsts) if firsts else None
    last = max(lasts) if lasts else None
    period = _fmt_period(first, last)

    crit_txt = t(f"{n_crit} crítico(s)", f"{n_crit} critical") if n_crit else t("sin críticos", "none critical")
    st.markdown(
        f"""
        <div style="background:#fff7ed;border:1px solid #fed7aa;
             border-left:6px solid #f29900;border-radius:10px;
             padding:0.7rem 1rem;margin:0.2rem 0 0.6rem 0">
          <span style="font-weight:700;color:#7c2d12">🔔 {t('Eventos críticos en la operación histórica', 'Critical events in the historical operation')}</span>
          <span style="color:#9a3412;font-size:0.9rem"> · {t(f'{len(alarms)} evento(s)', f'{len(alarms)} event(s)')}
          ({crit_txt}) {t('entre', 'between')} {period}.</span>
          <div style="color:#7c2d12;font-size:0.85rem;margin-top:4px">
            {t(
                "La vida útil simulada asume una operación nominal; estos episodios "
                "(seguridad / salud / garantía) pueden afectar a la degradación real y a "
                "la rentabilidad. Revisa el registro completo y el subelemento responsable.",
                "The simulated useful life assumes nominal operation; these episodes "
                "(safety / health / warranty) may affect real degradation and "
                "profitability. Review the full log and the responsible subelement.",
            )}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Acceso directo al registro completo (Vista de planta, encuadrado al periodo)
    # y al detalle de cada subelemento responsable.
    elements = []
    for alarm in alarms:
        el = _SUBELEMENT_TO_ELEMENT.get(alarm.subelement)
        if el and el not in elements:
            elements.append(el)

    cols = st.columns(1 + len(elements))
    cols[0].button(
        t("🔔 Ver registro en Vista de planta →", "🔔 View log in Plant View →"),
        key="sim_events_plant",
        on_click=_goto_plant_range, args=(first, last),
        use_container_width=True,
        help=t(
            "Abre el registro de eventos críticos al final de la Vista de planta, "
            "encuadrando el rango en la ventana de los eventos.",
            "Opens the critical events log at the end of the Plant View, framing the "
            "range to the events' window.",
        ),
    )
    for i, el in enumerate(elements):
        cols[i + 1].button(
            t(f"🔧 Ver detalle de {el} →", f"🔧 View {_element_label(el)} detail →"),
            key=f"sim_events_el_{i}",
            on_click=_goto_element, args=(el,),
            use_container_width=True,
        )
