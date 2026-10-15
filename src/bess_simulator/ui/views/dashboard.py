"""Dashboard de operación — SOLO VISUALIZACIÓN.

Consume el "dataset activo" generado en la pantalla de administración
(Generación de Datos). No expone parámetros de generación sintética: el
operador trabaja con el dataset como si fuera de datos reales.
"""

import streamlit as st
import pandas as pd

from bess_simulator.i18n import t
from bess_simulator.data.synthetic import aggregate_to_daily
from bess_simulator.data.export import export_dashboard_to_csv
from bess_simulator.ui.views.data_generation import ensure_active_dataset
from bess_simulator.ui.components.charts import (
    chart_dashboard_prices_income,
    chart_dashboard_soh,
    chart_dashboard_rte,
    chart_dashboard_cycles,
    chart_dashboard_temperature,
)


def _compute_variation(series):
    if len(series) < 2:
        return 0.0
    mid = len(series) // 2
    first_half = series.iloc[:mid].mean()
    second_half = series.iloc[mid:].mean()
    if first_half == 0:
        return 0.0
    return (second_half - first_half) / first_half


def render_dashboard_page():
    from bess_simulator.ui.components.sticky_header import render_sticky_header
    render_sticky_header("Dashboard Histórico BESS")
    render_dashboard_body()


def render_dashboard_body():
    """Cuerpo del dashboard histórico, sin cabecera fija.

    Se reutiliza tanto en la página independiente como embebido en una pestaña
    del Simulador ROI.
    """
    # Dataset activo (auto-generado con defaults la primera vez)
    bundle = ensure_active_dataset()
    df = bundle["df"]
    start, hoy, end = bundle["start"], bundle["hoy"], bundle["end"]

    if df.empty:
        st.warning(t("El dataset activo no contiene datos. Genera uno en **Generación de Datos**.", "The active dataset contains no data. Generate one in **Data Generation**."))
        return

    # --- Controles de visualización (no afectan a la generación) ---
    col_info, col_gran = st.columns([3, 2])
    with col_info:
        st.caption(
            t(
                f"**Dataset activo:** {bundle['label']}. "
                "Parametrízalo en **Datos & Modelo → Generación de Datos**.",
                f"**Active dataset:** {bundle['label']}. "
                "Configure it in **Data & Model → Data Generation**.",
            )
        )
    with col_gran:
        granularity = st.radio(
            t("Granularidad", "Granularity"), ["Daily", "15-min"], horizontal=True, key="db_gran",
            help=t("Daily = 1 dato/día (más rápido). 15-min = 96 datos/día (más detalle)", "Daily = 1 data point/day (faster). 15-min = 96 data points/day (more detail)"),
        )

    if granularity == "Daily":
        df_display = aggregate_to_daily(df)
    else:
        df_display = df

    hoy_ts = pd.Timestamp(str(hoy))
    hist = df_display[~df_display["is_forecast"]]
    fore = df_display[df_display["is_forecast"]]

    # --- KPI Cards (6) ---
    st.markdown("---")
    st.markdown(t("##### Histórico", "##### Historical"))
    h1, h2, h3 = st.columns(3)
    with h1:
        val = hist["income"].sum() if not hist.empty else 0
        st.metric(t("Income Histórico", "Historical Income"), f"{val:,.0f} €", delta=f"{_compute_variation(hist['income']):.2%}" if not hist.empty else "—")
    with h2:
        val = hist["capture_price"].mean() if not hist.empty else 0
        st.metric(t("Capture Price Hist.", "Hist. Capture Price"), f"{val:,.2f} €/MWh")
    with h3:
        val = hist["soh"].iloc[-1] if not hist.empty else 1.0
        st.metric(t("SoH actual", "Current SoH"), f"{val:.2%}")

    st.markdown(t("##### Proyección", "##### Forecast"))
    f1, f2, f3 = st.columns(3)
    with f1:
        val = fore["income"].sum() if not fore.empty else 0
        st.metric(t("Income Proyectado", "Forecast Income"), f"{val:,.0f} €", delta=f"{_compute_variation(fore['income']):.2%}" if not fore.empty else "—")
    with f2:
        val = fore["capture_price"].mean() if not fore.empty else 0
        st.metric(t("Capture Price Proy.", "Fcst. Capture Price"), f"{val:,.2f} €/MWh")
    with f3:
        val = fore["soh"].iloc[-1] if not fore.empty else 0
        st.metric(t("SoH final proyectado", "Final forecast SoH"), f"{val:.2%}")

    # --- Gráfico principal ---
    st.markdown(t("### Evolución temporal", "### Time evolution"))
    st.caption(t("Línea vertical = fecha HOY. Izquierda = histórico sintético OMIE. Derecha = proyección paramétrica", "Vertical line = TODAY's date. Left = synthetic OMIE history. Right = parametric forecast"))
    st.plotly_chart(
        chart_dashboard_prices_income(df_display, hoy_ts),
        use_container_width=True,
    )

    # --- Registro de eventos críticos (APM) ---
    # Movido a la Vista de planta (al final). Aquí ya no se muestra para evitar
    # duplicidad; el atajo del Simulador ROI enlaza con la Vista de planta.

    # --- Pestañas adicionales ---
    st.divider()
    tab_soh, tab_rte, tab_cycles, tab_temp = st.tabs(["SoH", "RTE", t("Ciclos", "Cycles"), t("Temperatura", "Temperature")])
    with tab_soh:
        st.plotly_chart(chart_dashboard_soh(df_display, hoy_ts), use_container_width=True)
    with tab_rte:
        st.plotly_chart(chart_dashboard_rte(df_display, hoy_ts), use_container_width=True)
    with tab_cycles:
        st.plotly_chart(chart_dashboard_cycles(df_display, hoy_ts), use_container_width=True)
    with tab_temp:
        st.plotly_chart(chart_dashboard_temperature(df_display, hoy_ts), use_container_width=True)

    # --- Exports ---
    st.divider()
    ex1, ex2, ex3 = st.columns(3)
    with ex1:
        st.download_button(
            t("Descargar datos completos (CSV)", "Download full data (CSV)"),
            data=export_dashboard_to_csv(df, "all"),
            file_name=f"bess_dashboard_{start}_{end}.csv",
            mime="text/csv",
        )
    with ex2:
        st.download_button(
            t("Descargar histórico (CSV)", "Download historical data (CSV)"),
            data=export_dashboard_to_csv(df, "historical"),
            file_name=f"bess_historico_{start}_{hoy}.csv",
            mime="text/csv",
        )
    with ex3:
        st.download_button(
            t("Descargar proyección (CSV)", "Download forecast (CSV)"),
            data=export_dashboard_to_csv(df, "forecast"),
            file_name=f"bess_proyeccion_{hoy}_{end}.csv",
            mime="text/csv",
        )
