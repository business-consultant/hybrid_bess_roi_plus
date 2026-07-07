from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
        st.info("No hay simulaciones guardadas todavía.")
        return

    df_sims = pd.DataFrame(sims)
    df_sims["label"] = df_sims.apply(
        lambda r: f"{r['name'] or r['id'][:8]} — {r['created_at'][:16]}", axis=1,
    )

    # --- Modo: Ver o Comparar ---
    mode = st.radio("Modo", ["Ver detalle", "Comparar"], horizontal=True, key="saved_mode", help="Ver detalle: análisis completo de una simulación. Comparar: métricas lado a lado de hasta 4 simulaciones")

    if mode == "Ver detalle":
        _render_detail_view(repo, df_sims)
    else:
        _render_compare_view(repo, df_sims)


def _render_detail_view(repo, df_sims):
    selected_label = st.selectbox("Selecciona una simulación", df_sims["label"], help="Selecciona una simulación guardada para revisar sus resultados")
    idx = df_sims[df_sims["label"] == selected_label].index[0]
    sim_id = df_sims.loc[idx, "id"]

    meta = repo.get_metadata(sim_id)
    if meta is None:
        st.error("Simulación no encontrada.")
        return

    render_kpi_cards(meta["roi"], meta["van"], discount_rate=meta["discount_rate"])

    col_params, col_results = st.columns(2)
    with col_params:
        st.markdown("##### Parámetros")
        params_display = {
            "CAPEX (€/MW)": f"{meta['capex_per_mw']:,.0f}",
            "OPEX (€/MW/año)": f"{meta['opex_per_mw_year']:,.0f}",
            "Tasa descuento": f"{meta['discount_rate']:.2%}",
            "Spread (€/MWh)": f"{meta['avg_spread_price']:.1f}",
            "Potencia (MW)": f"{meta['rated_power_mw']:.0f}",
            "C-Rate (MWh/MW)": f"{meta['c_rate_inverse']:.0f}",
            "Ciclos vida": f"{meta['eqo_cycles']:,.0f}",
            "Vida útil (años)": meta["lifespan_years"],
            "SoH inicial": f"{meta['initial_soh']:.2%}",
            "RTE": f"{meta['rte']:.2%}",
            "Degradación/ciclo": f"{meta['degradation_per_cycle']:.6f}",
            "SoH mín": f"{meta['soh_min']:.2%}",
            "DoD máx": f"{meta['max_dod']:.2%}",
            "Ciclos/año": f"{meta['year_cycles']:,.1f}",
        }
        st.dataframe(
            pd.DataFrame({"Parámetro": params_display.keys(), "Valor": params_display.values()}),
            hide_index=True,
            use_container_width=True,
        )

    with col_results:
        st.markdown("##### Resultados")
        st.metric("Incumplimientos SoH", meta["total_incumplimientos"])
        st.caption(f"Guardado: {meta['created_at']}")

    yearly = repo.load_yearly_summary(sim_id)
    inputs = repo.load_inputs(sim_id)

    tab1, tab2, tab3, tab4 = st.tabs(["Ingresos/Costes", "SoH", "Cash Flow", "Degradación/RTE"])
    with tab1:
        st.plotly_chart(chart_yearly_income_costs(yearly), use_container_width=True)
    with tab2:
        st.plotly_chart(chart_soh_evolution(yearly, inputs.efficiency.soh_min), use_container_width=True)
    with tab3:
        st.plotly_chart(chart_cash_flow(yearly), use_container_width=True)
    with tab4:
        st.plotly_chart(chart_degradation_rte(yearly), use_container_width=True)

    st.divider()
    if st.button("Eliminar esta simulación", type="secondary", help="Elimina permanentemente la simulación y sus datos asociados"):
        repo.delete(sim_id)
        st.rerun()


def _render_compare_view(repo, df_sims):
    selected = st.multiselect(
        "Selecciona simulaciones a comparar (máx. 4)",
        options=df_sims["label"].tolist(),
        max_selections=4,
        help="Selecciona 2-4 simulaciones para comparar ROI, VAN y parámetros lado a lado",
    )

    if len(selected) < 2:
        st.info("Selecciona al menos 2 simulaciones para comparar.")
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
        fig.update_layout(title="VAN (€)", template="plotly_white", height=350)
        st.plotly_chart(fig, use_container_width=True)

    compare_data = []
    for m, name in zip(metas, names):
        compare_data.append({
            "Simulación": name,
            "ROI": f"{m['roi']:.2%}",
            "VAN (€)": f"{m['van']:,.0f}",
            "CAPEX (€/MW)": f"{m['capex_per_mw']:,.0f}",
            "Spread (€/MWh)": f"{m['avg_spread_price']:.1f}",
            "Potencia (MW)": f"{m['rated_power_mw']:.0f}",
            "RTE": f"{m['rte']:.2%}",
            "Incumplimientos": m["total_incumplimientos"],
        })
    st.dataframe(pd.DataFrame(compare_data), hide_index=True, use_container_width=True)
