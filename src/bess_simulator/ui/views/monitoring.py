"""Elementos de planta: estado y detalle por subelemento (Fase 7).

Vista de análisis tipo Control Center. APM no es tiempo real: las tablas por
unidad resumen **variables agregadas sobre el periodo seleccionado** (máximos,
medias, disponibilidad). Ofrece:

  - una **vista general** con el panel agregado "BESS Data", el recuento de
    subelementos y tarjetas de acceso por equipo;
  - **pantallas de detalle** por subelemento: tablas por unidad para BESS (BMS)
    y PCS, y series temporales para meteo y climatización (HVAC).

La planta está **acoplada en AC**: los inversores del campo PV son los mismos
convertidores que el PCS del BESS, así que ambos se unifican en la tarjeta PCS.
El rango temporal de visualización es **compartido** con la vista de planta.
"""

import html

import streamlit as st

from bess_simulator.i18n import t
from bess_simulator.models.parameters import SimulationInputs, PvParams

from bess_simulator.engine.plant import compute_plant_summary, slice_bundle
from bess_simulator.engine import elements
from bess_simulator.engine.elements import STATUS_ICON, STATUS_LABEL
from bess_simulator.ui.components.charts import (
    chart_meteo_irradiance, chart_meteo_ambient,
    chart_pcs_specific_power, chart_bess_temperature,
    chart_hvac_cop_gauge, chart_hvac_consumption,
)
from bess_simulator.ui.views.data_generation import ensure_active_dataset


# Subelementos: (título, descripción, tipo de detalle). Los nombres se mantienen
# en español como claves internas (session_state, routing); solo se traduce la
# etiqueta mostrada en pantalla, vía ``_element_label``/``_element_desc``.
_SUBELEMENTS = [
    ("Módulos BESS", "Racks/contenedores de baterías", "bess"),
    ("PCS", "Inversores (acoplamiento AC: BESS + campo PV)", "pcs"),
    ("HVAC", "Climatización de los contenedores", "hvac"),
    ("Transformadores", "Elevadores y de servicios auxiliares", "transformer"),
    ("Estación meteorológica", "Irradiancia, temperatura, viento, humedad", "meteo"),
]
_SUBELEMENT_TYPE = {name: kind for name, _, kind in _SUBELEMENTS}

_ELEMENT_LABEL_EN = {
    "Módulos BESS": "BESS Modules",
    "PCS": "PCS",
    "HVAC": "HVAC",
    "Transformadores": "Transformers",
    "Estación meteorológica": "Weather Station",
}
_ELEMENT_DESC_EN = {
    "Racks/contenedores de baterías": "Battery racks/containers",
    "Inversores (acoplamiento AC: BESS + campo PV)": "Inverters (AC-coupled: BESS + PV field)",
    "Climatización de los contenedores": "Container air conditioning",
    "Elevadores y de servicios auxiliares": "Step-up and auxiliary service transformers",
    "Irradiancia, temperatura, viento, humedad": "Irradiance, temperature, wind, humidity",
}


def _element_label(name: str) -> str:
    return t(name, _ELEMENT_LABEL_EN.get(name, name))


def _goto_plant() -> None:
    st.session_state["nav_page"] = "Vista de planta"


def _select_element(name: str) -> None:
    st.session_state["monitoring_element"] = name


def _clear_element() -> None:
    st.session_state["monitoring_element"] = None


# ---------------------------------------------------------------------------
# Bloques reutilizables
# ---------------------------------------------------------------------------

def _status_legend() -> None:
    st.markdown(
        f"{STATUS_ICON['disponible']} {t(STATUS_LABEL['disponible'], 'Available')} &nbsp;·&nbsp; "
        f"{STATUS_ICON['aviso']} {t(STATUS_LABEL['aviso'], 'Warning')} &nbsp;·&nbsp; "
        f"{STATUS_ICON['fallo']} {t(STATUS_LABEL['fallo'], 'Fault')}",
        unsafe_allow_html=True,
    )


def _device_bar(label: str, count: int, max_count: int) -> None:
    pct = 0 if max_count <= 0 else max(8, round(100 * count / max_count))
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.5rem;margin:0.25rem 0">
          <div style="width:130px;color:#9aa4b2;font-size:0.85rem">{label}</div>
          <div style="flex:1;background:#243044;border-radius:5px;height:22px;position:relative">
            <div style="width:{pct}%;background:#2fae5f;height:100%;border-radius:5px"></div>
            <div style="position:absolute;top:0;left:0;width:100%;height:100%;
                 display:flex;align-items:center;justify-content:center;
                 color:#ffffff;font-size:0.78rem;font-weight:700">{count}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_left_panel(summary, panel: dict) -> None:
    """Panel lateral 'BESS Data' + 'Devices Data' (común a las pantallas)."""
    with st.container(border=True):
        st.markdown("#### BESS Data")
        a, b = st.columns(2)
        a.metric(t("Potencia activa", "Active power"), f"{panel['active_power_mw']:.1f} MW")
        b.metric(t("Energía exportada", "Energy exported"), f"{panel['energy_exported_mwh']:,.1f} MWh")
        a.metric(t("Potencia reactiva", "Reactive power"), f"{panel['reactive_power_mvar']:.1f} Mvar")
        b.metric(t("Energía importada", "Energy imported"), f"{panel['energy_imported_mwh']:,.1f} MWh")
        a.metric(t("Factor de potencia", "Power factor"), f"{panel['power_factor']:.2f}")
        b.metric(t("Factor de capacidad", "Capacity factor"), f"{panel['capacity_factor_pct']:.1f} %")

        st.markdown("#### Devices Data")
        counts = {
            "Meters": max(1, int(summary.meters)),
            "PCS": max(1, int(summary.pcs)),
            "BESS": max(1, int(summary.bess_modules)),
            "Power Station": max(1, int(summary.power_stations)),
        }
        top = max(counts.values())
        for label, count in counts.items():
            _device_bar(label, count, top)


def _render_scada_header(title: str) -> None:
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(
            '<span style="background:#2fae5f;color:#fff;font-weight:700;'
            f'padding:2px 10px;border-radius:5px;font-size:0.8rem">{t("Disponible", "Available")}</span>'
            '&nbsp;&nbsp;<span style="font-weight:700;font-size:1.05rem">'
            '🔋 BESS 001</span>',
            unsafe_allow_html=True,
        )
    with c2:
        st.button(t("← Volver", "← Back"), on_click=_clear_element, use_container_width=True)
    st.markdown(f"### {_element_label(title)}")


def _render_snapshot_table(snapshot) -> None:
    counts = elements.status_counts(snapshot)
    st.markdown(
        f"{STATUS_ICON['disponible']} {counts['disponible']} &nbsp;·&nbsp; "
        f"{STATUS_ICON['aviso']} {counts['aviso']} &nbsp;·&nbsp; "
        f"{STATUS_ICON['fallo']} {counts['fallo']} &nbsp; {t('equipos', 'units')}",
        unsafe_allow_html=True,
    )
    st.dataframe(
        snapshot.drop(columns=["_status"]),
        hide_index=True,
        use_container_width=True,
        height=520,
    )


# ---------------------------------------------------------------------------
# Pantallas de detalle por subelemento
# ---------------------------------------------------------------------------

def _render_warranty_header(kpis: list[dict], title: str | None = None) -> None:
    """Cabecera de tarjetas KPI con semáforo de estado.

    Cada tarjeta lleva un *semáforo*: borde e ícono en verde / ámbar / rojo
    según el ``status`` (las informativas se pintan en azul).
    """
    if title is None:
        title = t("Warranty compliance · resumen del grupo", "Warranty compliance · group summary")
    if not kpis:
        return
    accent = {
        elements.STATUS_AVAILABLE: "#2fae5f",
        elements.STATUS_WARNING: "#f1c40f",
        elements.STATUS_FAULT: "#e74c3c",
    }
    st.markdown(f"##### {title}")
    cols = st.columns(min(4, len(kpis)) or 1)
    n_cols = len(cols)
    for i, kpi in enumerate(kpis):
        status = kpi.get("status")
        color = accent.get(status, "#1F4BFF")
        dot = f"{STATUS_ICON[status]} " if status in STATUS_ICON else ""
        limit = kpi.get("limit")
        limit_html = (
            f'<div style="color:#6b7686;font-size:0.7rem;margin-top:1px">'
            f'{limit}</div>'
            if limit
            else ""
        )
        # Tooltip nativo (atributo HTML title) con un glifo ⓘ junto al título.
        help_text = kpi.get("help")
        help_html = (
            f'<span title="{html.escape(help_text, quote=True)}" '
            f'style="color:#6b7686;cursor:help;margin-left:4px">ⓘ</span>'
            if help_text
            else ""
        )
        card_title = f' title="{html.escape(help_text, quote=True)}"' if help_text else ""
        with cols[i % n_cols]:
            st.markdown(
                f"""
                <div{card_title} style="background:#11161f;border:1px solid #243044;
                     border-left:4px solid {color};border-radius:10px;
                     padding:0.55rem 0.8rem;margin-bottom:0.6rem">
                  <div style="color:#9aa4b2;font-size:0.72rem;text-transform:uppercase;
                       letter-spacing:0.04em">{dot}{kpi['title']}{help_html}</div>
                  <div style="color:#e6edf3;font-size:1.35rem;font-weight:700;
                       margin-top:2px">{kpi['value']}</div>
                  <div style="color:{color};font-size:0.8rem;font-weight:600;
                       margin-top:2px">{kpi['element']}</div>
                  {limit_html}
                </div>
                """,
                unsafe_allow_html=True,
            )


def _detail_bess(summary, bundle) -> None:
    cfg = st.session_state.get("app_config") or {}
    temp_critical = float(cfg.get("alarm_temp_critical_c", 40.0))
    snapshot = elements.build_bess_snapshot(summary, bundle.get("df"), temp_critical)
    thresholds = {
        "soh_min": float(cfg.get("alarm_soh_min", 0.80)) * 100.0,
        "cell_temp_max": temp_critical,
        "soh_spread_max": float(cfg.get("warranty_soh_spread_max_pp", 5.0)),
        "cycles_max": float(cfg.get("warranty_cycles_max", 6000.0)),
        "dod_max": float(cfg.get("warranty_dod_max_pct", 100.0)),
    }
    _render_warranty_header(
        elements.build_bess_warranty_kpis(snapshot, thresholds)
    )
    st.caption(
        t(
            "Indicadores agregados del periodo por módulo (carga, SoC, SoH, DoD "
            "máx., temperatura máx. de celda, desviación máx. de tensión, "
            "intensidad máx. y ciclos equivalentes). Datos sintéticos del prototipo.",
            "Period-aggregated indicators per module (charge, SoC, SoH, max DoD, "
            "max cell temperature, max voltage deviation, max current and "
            "equivalent cycles). Synthetic prototype data.",
        )
    )
    _render_snapshot_table(snapshot)


def _detail_pcs(summary, bundle) -> None:
    snapshot = elements.build_pcs_snapshot(summary, bundle.get("df"))
    st.caption(
        t(
            "Indicadores agregados del periodo por convertidor (PR del inversor, "
            "producción y disponibilidad). Planta acoplada en AC: el PCS es a la vez "
            "inversor del BESS y del campo PV. Datos sintéticos.",
            "Period-aggregated indicators per converter (inverter PR, production and "
            "availability). AC-coupled plant: the PCS is both the BESS inverter and "
            "the PV field inverter. Synthetic data.",
        )
    )
    _render_snapshot_table(snapshot)

    series = elements.build_pcs_power_series(summary, bundle)
    if series is not None and not series.empty:
        st.caption(
            t(
                "Potencia específica de cada inversor = potencia activa AC / potencia "
                "DC instalada (p.u.), magnitud comparable entre inversores con "
                "independencia de su tamaño. Una línea por inversor (media diaria) y "
                "la media del grupo destacada.",
                "Specific power of each inverter = active AC power / installed DC "
                "power (p.u.), a magnitude comparable across inverters regardless of "
                "size. One line per inverter (daily average) with the group average "
                "highlighted.",
            )
        )
        st.plotly_chart(
            chart_pcs_specific_power(series), use_container_width=True
        )


def _detail_meteo(summary, bundle) -> None:
    meteo = bundle.get("meteo")
    if meteo is None or meteo.empty:
        st.info(t("No hay serie meteorológica en el dataset activo.", "There is no weather series in the active dataset."))
        return
    st.caption(
        t(
            "Estación meteorológica a resolución nativa de 15 min: irradiancia "
            "(recurso solar) y condiciones ambientales.",
            "Weather station at native 15-min resolution: irradiance (solar "
            "resource) and ambient conditions.",
        )
    )
    pyranometers = elements.build_meteo_pyranometers(meteo)
    st.plotly_chart(chart_meteo_irradiance(pyranometers), use_container_width=True)
    st.plotly_chart(chart_meteo_ambient(meteo), use_container_width=True)


def _detail_hvac(summary, bundle) -> None:
    df = bundle.get("df")
    if df is None or df.empty or "temperature" not in df.columns:
        st.info(t("No hay serie de temperatura en el dataset activo.", "There is no temperature series in the active dataset."))
        return
    cfg = st.session_state.get("app_config") or {}
    temp_critical = float(cfg.get("alarm_temp_critical_c", 40.0))

    # Parámetros HVAC (objetivos de COP, uniformidad y disponibilidad). La
    # uniformidad admisible se ata por defecto a la franja de seguridad térmica.
    params = {
        "container_mwh": float(cfg.get("hvac_container_mwh", 5.0)),
        "cop_target": float(cfg.get("hvac_cop_target", 3.0)),
        "delta_t_max": float(cfg.get("hvac_delta_t_max_c", 5.0)),
        "availability_target": float(cfg.get("hvac_availability_target_pct", 98.0)),
        "hvac_share_pct": float(cfg.get("hvac_share_pct", 5.0)),
    }
    snapshot = elements.build_hvac_snapshot(summary, df, params)

    _render_warranty_header(
        elements.build_hvac_kpis(snapshot, summary, params),
        title=t("Climatización HVAC · resumen del grupo", "HVAC air conditioning · group summary"),
    )
    st.caption(
        t(
            "Indicadores agregados del periodo por contenedor (1 HVAC + 1 sistema "
            "de supresión por contenedor). COP en modo enfriamiento, uniformidad "
            "térmica ΔT entre sensores, consumo eléctrico y disponibilidad. "
            "Datos sintéticos del prototipo.",
            "Period-aggregated indicators per container (1 HVAC + 1 suppression "
            "system per container). Cooling-mode COP, thermal uniformity ΔT between "
            "sensors, electrical consumption and availability. Synthetic prototype "
            "data.",
        )
    )

    g1, g2 = st.columns([1, 2])
    with g1:
        cop_mean = float(snapshot["COP"].mean()) if not snapshot.empty else 0.0
        st.plotly_chart(
            chart_hvac_cop_gauge(cop_mean, target=params["cop_target"]),
            use_container_width=True,
        )
    with g2:
        series = elements.build_hvac_consumption_series(summary, bundle, params)
        st.plotly_chart(
            chart_hvac_consumption(series), use_container_width=True,
        )

    _render_snapshot_table(snapshot)

    st.caption(
        t(
            "Temperatura operativa del sistema BESS, vigilada por la climatización "
            "(HVAC). La línea roja marca el umbral crítico de seguridad.",
            "BESS system operating temperature, monitored by the air conditioning "
            "(HVAC). The red line marks the critical safety threshold.",
        )
    )
    st.plotly_chart(
        chart_bess_temperature(df, temp_critical=temp_critical),
        use_container_width=True,
    )


def _detail_transformer(summary, bundle) -> None:
    st.caption(
        t(
            "Transformadores elevadores y de servicios auxiliares. "
            "El detalle de telemetría se incorporará con la capa de datos eléctrica.",
            "Step-up and auxiliary service transformers. "
            "Telemetry detail will be added with the electrical data layer.",
        )
    )
    st.metric(t("Transformadores en servicio", "Transformers in service"), f"{max(1, int(summary.power_stations))}")
    _status_legend()


_DETAIL_RENDERERS = {
    "bess": _detail_bess,
    "pcs": _detail_pcs,
    "meteo": _detail_meteo,
    "hvac": _detail_hvac,
    "transformer": _detail_transformer,
}


def _render_detail(name: str, summary, bundle, panel: dict) -> None:
    _render_scada_header(name)
    left, right = st.columns([1.3, 3])
    with left:
        _render_left_panel(summary, panel)
        st.divider()
        _status_legend()
    with right:
        kind = _SUBELEMENT_TYPE.get(name, "transformer")
        _DETAIL_RENDERERS[kind](summary, bundle)


# ---------------------------------------------------------------------------
# Vista general
# ---------------------------------------------------------------------------

def _render_element_card(name: str, desc: str) -> None:
    with st.container(border=True):
        st.markdown(f"##### {_element_label(name)}")
        st.caption(t(desc, _ELEMENT_DESC_EN.get(desc, desc)))
        st.button(
            t("Ver detalle →", "View detail →"), key=f"open_{name}",
            on_click=_select_element, args=(name,),
            use_container_width=True,
        )


def _render_overview(summary, bundle, panel: dict) -> None:
    st.caption(t("Portfolio Híbrido › Planta › Elementos", "Hybrid Portfolio › Plant › Elements"))
    st.button(t("← Volver a la vista de planta", "← Back to plant view"), on_click=_goto_plant)

    left, right = st.columns([1.3, 3])
    with left:
        _render_left_panel(summary, panel)
    with right:
        st.markdown(t("#### Subelementos", "#### Subelements"))
        _status_legend()
        cols = st.columns(2)
        for i, (name, desc, _kind) in enumerate(_SUBELEMENTS):
            with cols[i % 2]:
                _render_element_card(name, desc)


def render_monitoring_page():
    from bess_simulator.ui.components.sticky_header import (
        render_sticky_header, render_view_range,
    )
    render_sticky_header("Elementos de Planta")

    bundle = ensure_active_dataset()

    # Rango de visualización compartido con la vista de planta (esquina sup. dcha.).
    sel = render_view_range(bundle)
    if isinstance(sel, tuple) and len(sel) == 2:
        sel_start, sel_end = sel
        st.caption(t(f"📅 Visualizando **{sel_start} → {sel_end}** · periodo común a todas las vistas.", f"📅 Viewing **{sel_start} → {sel_end}** · period common to all views."))
        view_bundle = slice_bundle(bundle, sel_start, sel_end)
    else:
        st.info(t("Selecciona un rango de visualización (fecha inicio y fin).", "Select a display range (start and end date)."))
        return

    inputs = st.session_state.get("inputs")
    if inputs is None:
        params = view_bundle.get("params", {})
        inputs = SimulationInputs(pv=PvParams(latitude=float(params.get("latitude", 40.0))))
        inputs.bess.rated_power_mw = float(params.get("rated_power_mw", 50))
    summary = compute_plant_summary(view_bundle, inputs)
    panel = elements.build_panel_data(summary, view_bundle.get("df"))

    selected = st.session_state.get("monitoring_element")
    if selected and selected in _SUBELEMENT_TYPE:
        _render_detail(selected, summary, view_bundle, panel)
    else:
        _render_overview(summary, view_bundle, panel)
