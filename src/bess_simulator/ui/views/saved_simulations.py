from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bess_simulator.i18n import t
from bess_simulator.ui.components.kpi_cards import render_kpi_cards
from bess_simulator.ui.components.charts import (
    chart_yearly_income_costs,
    chart_soh_evolution,
    chart_cash_flow,
    chart_degradation_rte,
)


def render_saved_simulations_page():
    from bess_simulator.ui.components.sticky_header import render_sticky_header
    render_sticky_header("Simulaciones Guardadas")

    repo = st.session_state["sim_repo"]
    sims = repo.list_all()

    if not sims:
        st.info(t("No hay simulaciones guardadas todavía.", "There are no saved simulations yet."))
        return

    df_sims = pd.DataFrame(sims)
    df_sims["label"] = df_sims.apply(
        lambda r: f"{r['name'] or r['id'][:8]} — {r['created_at'][:16]}", axis=1,
    )

    # --- Modo: Ver o Comparar ---
    mode = st.radio(
        t("Modo", "Mode"), [t("Ver detalle", "View detail"), t("Comparar", "Compare")], horizontal=True, key="saved_mode",
        help=t("Ver detalle: análisis completo de una simulación. Comparar: métricas lado a lado de hasta 4 simulaciones", "View detail: full analysis of one simulation. Compare: side-by-side metrics for up to 4 simulations"),
    )

    if mode == t("Ver detalle", "View detail"):
        _render_detail_view(repo, df_sims)
    else:
        _render_compare_view(repo, df_sims)


def _render_detail_view(repo, df_sims):
    selected_label = st.selectbox(t("Selecciona una simulación", "Select a simulation"), df_sims["label"], help=t("Selecciona una simulación guardada para revisar sus resultados", "Select a saved simulation to review its results"))
    idx = df_sims[df_sims["label"] == selected_label].index[0]
    sim_id = df_sims.loc[idx, "id"]

    meta = repo.get_metadata(sim_id)
    if meta is None:
        st.error(t("Simulación no encontrada.", "Simulation not found."))
        return

    render_kpi_cards(meta["roi"], meta["van"], discount_rate=meta["discount_rate"])

    col_params, col_results = st.columns(2)
    with col_params:
        st.markdown(t("##### Parámetros", "##### Parameters"))
        params_display = {
            t("CAPEX (€/MW)", "CAPEX (€/MW)"): f"{meta['capex_per_mw']:,.0f}",
            t("OPEX (€/MW/año)", "OPEX (€/MW/year)"): f"{meta['opex_per_mw_year']:,.0f}",
            t("Tasa descuento", "Discount rate"): f"{meta['discount_rate']:.2%}",
            t("Spread (€/MWh)", "Spread (€/MWh)"): f"{meta['avg_spread_price']:.1f}",
            t("Potencia (MW)", "Power (MW)"): f"{meta['rated_power_mw']:.0f}",
            t("C-Rate (MWh/MW)", "C-Rate (MWh/MW)"): f"{meta['c_rate_inverse']:.0f}",
            t("Ciclos vida", "Lifetime cycles"): f"{meta['eqo_cycles']:,.0f}",
            t("Vida útil (años)", "Useful life (years)"): meta["lifespan_years"],
            t("SoH inicial", "Initial SoH"): f"{meta['initial_soh']:.2%}",
            "RTE": f"{meta['rte']:.2%}",
            t("Degradación/ciclo", "Degradation/cycle"): f"{meta['degradation_per_cycle']:.6f}",
            t("SoH mín", "Min SoH"): f"{meta['soh_min']:.2%}",
            t("DoD máx", "Max DoD"): f"{meta['max_dod']:.2%}",
            t("Ciclos/año", "Cycles/year"): f"{meta['year_cycles']:,.1f}",
        }
        st.dataframe(
            pd.DataFrame({t("Parámetro", "Parameter"): params_display.keys(), t("Valor", "Value"): params_display.values()}),
            hide_index=True,
            use_container_width=True,
        )

    with col_results:
        st.markdown(t("##### Resultados", "##### Results"))
        st.metric(t("Incumplimientos SoH", "SoH breaches"), meta["total_incumplimientos"])
        st.caption(t(f"Guardado: {meta['created_at']}", f"Saved: {meta['created_at']}"))

    yearly = repo.load_yearly_summary(sim_id)
    inputs = repo.load_inputs(sim_id)

    tab1, tab2, tab3, tab4 = st.tabs([t("Ingresos/Costes", "Income/Costs"), "SoH", "Cash Flow", t("Degradación/RTE", "Degradation/RTE")])
    with tab1:
        st.plotly_chart(chart_yearly_income_costs(yearly), use_container_width=True)
    with tab2:
        st.plotly_chart(chart_soh_evolution(yearly, inputs.efficiency.soh_min), use_container_width=True)
    with tab3:
        st.plotly_chart(chart_cash_flow(yearly), use_container_width=True)
    with tab4:
        st.plotly_chart(chart_degradation_rte(yearly), use_container_width=True)

    st.divider()
    if st.button(t("Eliminar esta simulación", "Delete this simulation"), type="secondary", help=t("Elimina permanentemente la simulación y sus datos asociados", "Permanently deletes the simulation and its associated data")):
        repo.delete(sim_id)
        st.rerun()


def _render_compare_view(repo, df_sims):
    selected = st.multiselect(
        t("Selecciona simulaciones a comparar (máx. 4)", "Select simulations to compare (max. 4)"),
        options=df_sims["label"].tolist(),
        max_selections=4,
        help=t("Selecciona 2-4 simulaciones para comparar ROI, VAN y parámetros lado a lado", "Select 2-4 simulations to compare ROI, NPV and parameters side by side"),
    )

    if len(selected) < 2:
        st.info(t("Selecciona al menos 2 simulaciones para comparar.", "Select at least 2 simulations to compare."))
        return

    ids = [df_sims[df_sims["label"] == lbl].iloc[0]["id"] for lbl in selected]
    names = [df_sims[df_sims["label"] == lbl].iloc[0]["name"] or lbl[:8] for lbl in selected]
    metas = [repo.get_metadata(sid) for sid in ids]

    rois = [m["roi"] for m in metas]
    vans = [m["van"] for m in metas]

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Bar(x=names, y=[r * 100 for r in rois], marker_color="#3498db"))
        fig.update_layout(title="ROI (%)", template="plotly_white", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure(go.Bar(x=names, y=vans, marker_color="#2ecc71"))
        fig.update_layout(title=t("VAN (€)", "NPV (€)"), template="plotly_white", height=350)
        st.plotly_chart(fig, use_container_width=True)

    compare_data = []
    for m, name in zip(metas, names):
        compare_data.append({
            t("Simulación", "Simulation"): name,
            "ROI": f"{m['roi']:.2%}",
            t("VAN (€)", "NPV (€)"): f"{m['van']:,.0f}",
            t("CAPEX (€/MW)", "CAPEX (€/MW)"): f"{m['capex_per_mw']:,.0f}",
            t("Spread (€/MWh)", "Spread (€/MWh)"): f"{m['avg_spread_price']:.1f}",
            t("Potencia (MW)", "Power (MW)"): f"{m['rated_power_mw']:.0f}",
            "RTE": f"{m['rte']:.2%}",
            t("Incumplimientos", "Breaches"): m["total_incumplimientos"],
        })
    st.dataframe(pd.DataFrame(compare_data), hide_index=True, use_container_width=True)
