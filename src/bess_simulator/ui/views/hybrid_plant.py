"""Pantalla general de la planta híbrida PV+BESS (Fase 6).

Panel de control de operación inspirado en el dashboard de planta (tema claro):
especificaciones del activo, energía entregada, KPIs operativos, producción
diaria y un perfil intradiario a 5 minutos (PV + carga/descarga BESS + SoC).
Incluye un acceso directo a la monitorización de subelementos (Fase 7).
"""

import streamlit as st
from datetime import timedelta

from bess_simulator.i18n import t
from bess_simulator.models.parameters import SimulationInputs, PvParams
from bess_simulator.engine.plant import (
    compute_plant_summary,
    compute_kpi_deviations,
    compute_pv_kpi_deviations,
    build_power_soc_series,
    build_daily_production,
    slice_bundle,
    SHOWCASE_START,
    SHOWCASE_END,
)
from bess_simulator.ui.views.data_generation import ensure_active_dataset
from bess_simulator.ui.components.alerts_panel import render_alerts_panel
from bess_simulator.ui.components.charts import (
    chart_plant_energy_split,
    chart_plant_production,
    chart_power_soc_series,
)


def _resolve_inputs(bundle: dict) -> SimulationInputs:
    """Usa la simulación activa del operador o reconstruye defaults coherentes.

    Si el operador todavía no ha simulado, toma el dimensionado del dataset
    activo (potencia, latitud del emplazamiento) para no mostrar una planta
    incoherente con los datos.
    """
    inputs = st.session_state.get("inputs")
    if inputs is not None:
        return inputs

    params = bundle.get("params", {})
    rated = float(params.get("rated_power_mw", 50))
    c_rate_inv = float(params.get("c_rate_inverse", 4))
    latitude = float(params.get("latitude", 40.0))
    inputs = SimulationInputs(pv=PvParams(latitude=latitude))
    inputs.bess.rated_power_mw = rated
    inputs.bess.c_rate_inverse = c_rate_inv
    return inputs


def _goto_monitoring() -> None:
    st.session_state["nav_page"] = "Elementos de planta"


def render_hybrid_plant_page():
    from bess_simulator.ui.components.sticky_header import (
        render_sticky_header, ensure_view_range,
    )
    render_sticky_header("Planta Híbrida PV + BESS")

    bundle = ensure_active_dataset()
    inputs = _resolve_inputs(bundle)

    start_d, end_d = bundle["start"], bundle["end"]

    # --- Cabecera: breadcrumb + selector de planta + rango de visualización ---
    # El rango (clave compartida 'view_range') es común con la vista de elementos.
    ensure_view_range(bundle)
    col_bc, col_sel, col_range = st.columns([2, 2, 3])
    with col_bc:
        st.caption(t("Portfolio Híbrido › Planta", "Hybrid Portfolio › Plant"))
    with col_sel:
        st.selectbox(t("Planta", "Plant"), ["Planta Híbrida 1"], format_func=lambda _: t("Planta Híbrida 1", "Hybrid Plant 1"), label_visibility="collapsed")
    with col_range:
        st.markdown(
            '<div style="text-align:right;color:#9aa4b2;font-size:0.78rem;'
            f'margin-bottom:-0.4rem">📅 {t("Rango de visualización", "Display range")}</div>',
            unsafe_allow_html=True,
        )
        sel = st.date_input(
            t("Rango de visualización", "Display range"),
            min_value=start_d, max_value=end_d,
            key="view_range",
            label_visibility="collapsed",
            help=t(
                "Periodo aplicado a todos los KPIs y variables de esta vista y de "
                "la vista de elementos. No afecta a la vida útil del ROI.",
                "Period applied to all KPIs and variables in this view and in the "
                "elements view. Does not affect the ROI's useful life.",
            ),
        )

    if not isinstance(sel, tuple) or len(sel) != 2:
        st.info(t("Selecciona un rango de visualización (fecha inicio y fin).", "Select a display range (start and end date)."))
        return
    sel_start, sel_end = sel
    st.caption(
        t(
            f"📅 Visualizando **{sel_start} → {sel_end}** · "
            "el rango solo afecta a esta vista, no a la vida útil del ROI.",
            f"📅 Viewing **{sel_start} → {sel_end}** · "
            "the range only affects this view, not the ROI's useful life.",
        )
    )

    # Todas las vistas reaccionan a la misma fuente recortada (coherencia).
    view_bundle = slice_bundle(bundle, sel_start, sel_end)
    summary = compute_plant_summary(view_bundle, inputs)

    tab_perf, tab_econ, tab_quality = st.tabs(
        [t("Rendimiento", "Performance"), t("Económico", "Economic"), t("Calidad de datos", "Data quality")]
    )

    with tab_perf:
        _render_performance(view_bundle, inputs, summary, (sel_start, sel_end))
    with tab_econ:
        _render_economic()
    with tab_quality:
        _render_quality(view_bundle)


def _render_performance(bundle, inputs, summary, view_range):
    c1, c2, c3 = st.columns(3)

    # --- Especificaciones del activo ---
    with c1:
        with st.container(border=True):
            st.markdown(t("##### Especificaciones del activo", "##### Asset specifications"))
            st.markdown(f"**{t('Ubicación', 'Location')}**  ·  {summary.location}")
            st.markdown(f"**{t('Potencia nominal BESS', 'BESS rated power')}**  ·  {summary.nominal_power_mw:,.2f} MW")
            st.markdown(f"**{t('Capacidad BESS', 'BESS capacity')}**  ·  {summary.bess_capacity_mwh:,.2f} MWh")
            st.markdown(f"**{t('Potencia pico PV', 'PV peak power')}**  ·  {summary.pv_peak_mwp:,.2f} MWp")
            st.markdown(f"**{t('Inversor PV (AC)', 'PV inverter (AC)')}**  ·  {summary.pv_inverter_mw:,.2f} MW")
            st.markdown(f"**ILR (DC/AC)**  ·  {summary.ilr:.2f}")
            st.markdown(f"**{t('Límite POI', 'POI limit')}**  ·  {summary.poi_limit_mw:,.2f} MW")

    # --- Energía total entregada ---
    with c2:
        with st.container(border=True):
            st.markdown(t("##### Energía total entregada", "##### Total energy delivered"))
            st.plotly_chart(
                chart_plant_energy_split(summary.exported_pct, summary.imported_pct),
                use_container_width=True,
            )
            e1, e2 = st.columns([3, 2])
            e1.markdown(f"🔵 **{t('Exportada', 'Exported')}**")
            e2.markdown(f"**{summary.exported_gwh:,.2f} GWh**")
            e1.markdown(f"🔷 **{t('Importada', 'Imported')}**")
            e2.markdown(f"**{summary.imported_gwh:,.2f} GWh**")
            e1.markdown(f"☀️ **{t('PV generada', 'PV generated')}**")
            e2.markdown(f"**{summary.pv_generated_gwh:,.2f} GWh**")
            e1.markdown(f"**{t('Neto', 'Net')}**")
            e2.markdown(f"**{summary.net_mwh:,.2f} MWh**")

    # --- Acceso a subelementos (Mejora 2) ---
    with c3:
        _render_subelements_panel(summary)

    # --- Fila de KPIs con desvío frente al valor esperado ---
    df = bundle.get("df")
    n_days = int(df["timestamp"].dt.normalize().nunique()) if df is not None and not df.empty else 0
    devs = compute_kpi_deviations(summary, inputs, n_days)

    st.markdown("")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    _kpi_metric(k1, t("Disponibilidad", "Availability"), f"{summary.time_based_availability:.2f} %", devs["availability"])
    _kpi_metric(k2, t("Rango de SoC", "SoC range"), f"{summary.soc_min_pct:.0f}–{summary.soc_max_pct:.0f} %", devs["soc_range"])
    _kpi_metric(k3, t("Round-trip eff.", "Round-trip eff."), f"{summary.roundtrip_efficiency:.2%}", devs["rte"])
    _kpi_metric(k4, t("Nº de ciclos", "No. of cycles"), f"{summary.cycle_count:,.1f}", devs["cycles"])
    _kpi_metric(k5, t("State of health", "State of health"), f"{summary.state_of_health:.2%}", devs["soh"])
    _kpi_metric(k6, t("Pot. media", "Avg. power"), f"{summary.charge_discharge_avg_power_mw:,.2f} MW", devs["avg_power"])
    st.caption(t("ⁿ Superíndice: desvío % frente al valor de negocio deseable (🟢 favorable · 🔴 desfavorable).", "ⁿ Superscript: % deviation against the desired business value (🟢 favorable · 🔴 unfavorable)."))

    # --- Fila de KPIs fotovoltaicos ---
    pv_devs = compute_pv_kpi_deviations(summary, inputs)
    st.markdown("")
    st.markdown(t("###### ☀️ Fotovoltaica", "###### ☀️ Photovoltaic"))
    p1, p2, p3, p4, p5 = st.columns(5)
    _kpi_metric(p1, "PV Capacity factor", f"{summary.pv_capacity_factor:.1%}", pv_devs["pv_capacity_factor"])
    _kpi_metric(p2, "PV Performance ratio", f"{summary.pv_performance_ratio:.1%}", pv_devs["pv_performance_ratio"])
    _kpi_metric(p3, t("PV Disponibilidad", "PV Availability"), f"{summary.pv_availability:.2f} %", pv_devs["pv_availability"])
    _kpi_metric(p4, t("Irradiación", "Irradiation"), _format_irradiation(summary.pv_irradiation_wh_m2), pv_devs["pv_irradiation"])
    _kpi_metric(p5, t("PV Producción", "PV Production"), _format_energy(summary.pv_production_mwh), pv_devs["pv_production"])
    st.caption(
        t(
            "PV CF sobre la potencia AC del inversor · PR según IEC 61724 · "
            "disponibilidad técnica en horas de sol · irradiación POA acumulada en el periodo.",
            "PV CF over the inverter's AC power · PR per IEC 61724 · "
            "technical availability during sunlight hours · accumulated POA irradiation over the period.",
        )
    )

    # Rango X compartido por ambas gráficas (incluye el último día completo).
    x_range = (view_range[0], view_range[1] + timedelta(days=1))

    # --- Producción diaria ---
    st.markdown(t("### Producción diaria", "### Daily production"))
    st.caption(t("Barras: carga (−) y descarga (+) de la BESS por día. Línea: SoH.", "Bars: BESS charge (−) and discharge (+) per day. Line: SoH."))
    daily = build_daily_production(bundle, inputs)
    st.plotly_chart(chart_plant_production(daily, x_range=x_range), use_container_width=True)

    # --- Serie potencia PV+BESS y SoC (mismo eje temporal que arriba) ---
    st.markdown(t("### Potencia PV + BESS y SoC", "### PV + BESS power and SoC"))
    st.caption(
        t(
            "Potencia PV, carga/descarga de la BESS (+ descarga / − carga) y estado de "
            "carga (SoC), encadenando varias estrategias de despacho a lo largo del rango "
            "(arbitraje, arbitraje + secundaria, energy shifting y caso de uso multiservicio). "
            "**Nota**: la FV se recorta con una meseta plana en 50 MW cuando alcanza el límite del POI, y la descarga BESS se desplaza a 20-24h para usar solo margen nocturno disponible.",
            "PV power, BESS charge/discharge (+ discharge / − charge) and state of "
            "charge (SoC), chaining several dispatch strategies across the range "
            "(arbitrage, arbitrage + secondary, energy shifting and the multiservice use case). "
            "**Note**: PV is clipped with a flat plateau at 50 MW when it reaches the POI limit, and BESS discharge shifts to 20-24h to use only the available overnight headroom.",
        )
    )
    # Si la ventana del caso de uso garantizado está visible, mostramos las fases.
    show_start, show_end = SHOWCASE_START.date(), SHOWCASE_END.date()
    if view_range[0] <= show_end and view_range[1] >= show_start:
        st.caption(
            t(
                f"🎯 **Caso de uso multiservicio** ({show_start} → {show_end}): "
                "**00–06h** carga de red (precio bajo) · **06–14h** FV + carga de "
                "excedentes · **14–20h** modulación/carga suave sin exportación positiva · "
                "**18–22h** banda aFRR absorbente (sin conflicto con el POI) · "
                "**20–24h** descarga nocturna (máxima inyección sin PV).",
                f"🎯 **Multiservice use case** ({show_start} → {show_end}): "
                "**00–06h** grid charging (low price) · **06–14h** PV + surplus "
                "charging · **14–20h** modulation/gentle charging with no positive "
                "export · **18–22h** absorbing aFRR band (no conflict with the POI) · "
                "**20–24h** overnight discharge (maximum injection without PV).",
            )
        )
    series = build_power_soc_series(bundle, inputs)
    st.plotly_chart(chart_power_soc_series(series, x_range=x_range), use_container_width=True)

    # --- Registro de eventos críticos (APM) — al final de la vista ---
    # Coherente con el rango seleccionado: solo se listan los eventos cuyo
    # histórico cae dentro de la ventana de visualización activa.
    st.divider()
    render_alerts_panel(bundle.get("df"), cfg=st.session_state.get("app_config"))


def _format_irradiation(wh_m2: float) -> str:
    """Formatea la irradiación acumulada en kWh/m² (o Wh/m² si es pequeña)."""
    if wh_m2 >= 1000.0:
        return f"{wh_m2 / 1000.0:,.1f} kWh/m²"
    return f"{wh_m2:,.0f} Wh/m²"


def _format_energy(mwh: float) -> str:
    """Formatea energía en GWh si es grande, en MWh en caso contrario."""
    if mwh >= 1000.0:
        return f"{mwh / 1000.0:,.2f} GWh"
    return f"{mwh:,.1f} MWh"


def _kpi_metric(col, label: str, value: str, deviation_pct: float) -> None:
    """Renderiza un KPI con un superíndice de desvío % coloreado (verde/rojo)."""
    color = "#28a745" if deviation_pct >= 0 else "#dc3545"
    sign = "+" if deviation_pct >= 0 else ""
    col.markdown(
        f"""
        <div style="line-height:1.15">
          <div style="font-size:0.78rem;color:#6c757d;margin-bottom:2px">{label}</div>
          <div style="font-size:1.5rem;font-weight:600">{value}<sup style="font-size:0.68rem;
               color:{color};font-weight:700;margin-left:3px">{sign}{deviation_pct:.1f}%</sup></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_subelements_panel(summary):
    with st.container(border=True):
        st.markdown(t("##### Subelementos", "##### Subelements"))
        st.caption(t("Estado de los equipos de la planta", "Status of the plant's equipment"))
        d1, d2 = st.columns([3, 1])
        for label, count in (
            (t("Contadores", "Meters"), summary.meters),
            ("PCS", summary.pcs),
            (t("Módulos BESS", "BESS modules"), summary.bess_modules),
            ("Power Stations", summary.power_stations),
        ):
            d1.markdown(f"🟢 {label}")
            d2.markdown(f"**{count}**")
        st.caption(t("🟢 Disponible · 🔴 Fallo · 🟡 Aviso · 🔵 Parado", "🟢 Available · 🔴 Fault · 🟡 Warning · 🔵 Stopped"))
        st.button(
            t("Abrir elementos de planta ↗", "Open plant elements ↗"),
            use_container_width=True,
            on_click=_goto_monitoring,
            help=t("Accede al detalle de subelementos (PCS, BESS, HVAC, trafos, meteo, inversores PV)", "Access the subelement detail (PCS, BESS, HVAC, transformers, weather, PV inverters)"),
        )


def _go_to_dashboard():
    """Navega al Simulador ROI (el Dashboard Histórico vive en su pestaña)."""
    st.session_state["nav_page"] = "Simulador ROI"


def _render_economic():
    st.markdown(t("##### Análisis económico histórico", "##### Historical economic analysis"))
    st.caption(
        t(
            "El detalle económico de la planta (precios, ingresos, SoH, RTE, ciclos "
            "y temperatura sobre el histórico) vive en la pestaña **Dashboard Histórico "
            "BESS** dentro del **Simulador ROI**.",
            "The plant's economic detail (prices, income, SoH, RTE, cycles and "
            "temperature over the historical data) lives in the **BESS Historical "
            "Dashboard** tab inside the **ROI Simulator**.",
        )
    )
    st.button(
        t("📊 Abrir Dashboard Histórico BESS", "📊 Open BESS Historical Dashboard"),
        type="primary",
        on_click=_go_to_dashboard,
        help=t("Abre el Simulador ROI; selecciona la pestaña «Dashboard Histórico BESS».", "Opens the ROI Simulator; selects the «BESS Historical Dashboard» tab."),
    )


def _render_quality(bundle):
    df = bundle.get("df")
    if df is None or df.empty:
        st.warning(t("El dataset activo no contiene datos.", "The active dataset contains no data."))
        return
    q1, q2, q3 = st.columns(3)
    q1.metric(t("Intervalos", "Intervals"), f"{len(df):,}")
    q2.metric(t("Cobertura", "Coverage"), f"{bundle['start']} → {bundle['end']}")
    missing = float(df.isna().mean().mean()) * 100.0
    q3.metric(t("Datos faltantes", "Missing data"), f"{missing:.2f} %")
    st.caption(t("Calidad del dataset sintético activo (histórico + proyección).", "Quality of the active synthetic dataset (historical + forecast)."))
