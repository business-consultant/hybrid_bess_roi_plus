import streamlit as st

from bess_simulator.models.results import RevenueBreakdown, HybridEconomics


# Bandas de claridad para separar visualmente los grupos de KPIs dentro del
# desplegable "Más resultados" (clases st-key-* generadas por st.container(key=)).
_KPI_BAND_CSS = """
<style>
.st-key-kpi-band-hybrid,
.st-key-kpi-band-revenue,
.st-key-kpi-band-flows {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 10px;
    padding: 0.7rem 1.1rem 0.3rem 1.1rem;
    margin-bottom: 0.85rem;
}
.st-key-kpi-band-hybrid h4,
.st-key-kpi-band-revenue h4,
.st-key-kpi-band-flows h4 {
    margin-top: 0.1rem;
}
</style>
"""


def render_economic_kpis(results, inputs) -> None:
    """Salida de KPIs económicos del simulador.

    Muestra siempre la primera fila (ROI / VAN) y pliega el resto en un
    desplegable "Más resultados", con bandas de claridad que agrupan los
    distintos significados (rentabilidad por activo, streams, flujos POI).
    """
    st.markdown(_KPI_BAND_CSS, unsafe_allow_html=True)
    discount = inputs.economic.discount_rate

    render_kpi_cards(results.roi, results.van, discount_rate=discount)

    if results.hybrid is None:
        return

    with st.expander("Más resultados", expanded=False):
        with st.container(key="kpi-band-hybrid"):
            render_hybrid_kpis(results.roi, results.van, results.hybrid, discount_rate=discount)
        with st.container(key="kpi-band-synergy"):
            render_hybrid_synergy(results.hybrid)
        if results.revenue_breakdown.total > 0:
            with st.container(key="kpi-band-revenue"):
                render_revenue_breakdown(results.revenue_breakdown)
        with st.container(key="kpi-band-flows"):
            render_hybrid_flows(results.hybrid)


def render_kpi_cards(roi: float, van: float, discount_rate: float = 0.06):
    col1, col2 = st.columns(2)

    with col1:
        if roi > discount_rate:
            delta_text, delta_color = "Rentable", "normal"
        elif roi > 0:
            delta_text, delta_color = "Rentabilidad baja", "off"
        else:
            delta_text, delta_color = "No rentable", "inverse"
        st.metric("ROI (anualizado)", f"{roi:.2%}", delta=delta_text, delta_color=delta_color)
        st.caption(f"Retorno anualizado sobre inversión. > tasa descuento ({discount_rate:.0%}) = rentable")

    with col2:
        van_color = "normal" if van >= 0 else "inverse"
        st.metric("VAN (NPV)", f"{van:,.0f} €", delta="Positivo" if van >= 0 else "Negativo", delta_color=van_color)
        st.caption("Valor Actual Neto: suma de flujos de caja descontados − CAPEX. > 0 = genera valor")


def render_hybrid_kpis(
    bess_roi: float,
    bess_van: float,
    hybrid: HybridEconomics,
    discount_rate: float = 0.06,
):
    """KPIs de planta híbrida: ROI BESS y ROI PV por separado.

    El ROI de la BESS y el de la PV son independientes (no comparten CAPEX).
    """
    st.markdown("#### Rentabilidad por activo (BESS vs PV)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("ROI BESS (anualizado)", f"{bess_roi:.2%}")
        st.caption("Solo CAPEX/OPEX de la batería. No incluye la inversión PV")
    with c2:
        st.metric("ROI PV (anualizado)", f"{hybrid.pv_roi:.2%}")
        st.caption("Economía independiente del campo solar (CAPEX/OPEX PV)")
    with c3:
        plant_van = bess_van + hybrid.pv_van + hybrid.synergy_pv_charge_credit
        van_color = "normal" if plant_van >= 0 else "inverse"
        st.metric("VAN planta (BESS + PV)", f"{plant_van:,.0f} €", delta_color=van_color)
        st.caption("VAN BESS + VAN PV + crédito de sinergia PV→BESS")


def render_hybrid_synergy(hybrid: HybridEconomics):
    """Reconciliación energética PV↔BESS: carga solar, spread efectivo, curtailment.

    Cierra la fisura de valor: la energía PV→BESS se asigna a coste CERO y el
    ahorro de carga de red se reconoce como crédito de sinergia (vitamina el
    spread del BESS). El curtailment se estima (no se asume cero) y su coste
    ajusta la producción PV vendible.
    """
    st.markdown("#### Reconciliación PV↔BESS (sinergia y curtailment)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Carga BESS de origen solar",
        f"{hybrid.bess_solar_fraction:.1%}",
        help=(
            f"f_PV: fracción de la demanda anual de carga de la BESS cubierta por "
            f"la PV a coste cero. Carga solar: {hybrid.bess_solar_charge_mwh:,.0f} MWh "
            f"sobre {hybrid.bess_charge_demand_mwh:,.0f} MWh de demanda de carga"
        ),
    )
    c2.metric(
        "Spread efectivo",
        f"{hybrid.bess_effective_spread:,.1f} €/MWh",
        delta=f"+{hybrid.bess_effective_spread - hybrid.bess_base_spread:,.1f} vs base",
        delta_color="normal",
        help="Spread base vitaminado por la carga solar gratuita (ahorro de compra en pool)",
    )
    c3.metric(
        "Crédito de sinergia PV→BESS",
        f"{hybrid.synergy_pv_charge_credit:,.0f} €",
        help="Ahorro de vida útil (descontado) por cargar la BESS con PV en lugar de comprar en pool",
    )
    c4.metric(
        "Coste del curtailment",
        f"{hybrid.pv_curtailment_cost_total:,.0f} €",
        delta_color="off",
        help=(
            f"Ingreso PV perdido (vida útil) por el curtailment estimado: "
            f"{hybrid.pv_curtailment_total_mwh:,.0f} MWh/año "
            f"({hybrid.pv_curtailed_concurrency_mwh:,.0f} por concurrencia POI)"
        ),
    )


def render_revenue_breakdown(breakdown: RevenueBreakdown):
    """Desglose de los ingresos del BESS por stream (a/b/c/d)."""
    total = breakdown.total
    if total <= 0:
        return
    st.markdown("#### Ingresos BESS por stream (vida útil)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Arbitraje", f"{breakdown.arbitrage:,.0f} €", delta=f"{breakdown.arbitrage / total:.0%}", delta_color="off")
    c2.metric("PPA", f"{breakdown.ppa:,.0f} €", delta=f"{breakdown.ppa / total:.0%}", delta_color="off")
    c3.metric("Capacidad", f"{breakdown.capacity:,.0f} €", delta=f"{breakdown.capacity / total:.0%}", delta_color="off")
    c4.metric("Secundaria", f"{breakdown.secondary:,.0f} €", delta=f"{breakdown.secondary / total:.0%}", delta_color="off")


def render_hybrid_flows(hybrid: HybridEconomics):
    """Flujos de energía en el POI (año representativo)."""
    st.markdown("#### Flujos híbridos en el POI (año representativo)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PV → red (neto)", f"{hybrid.pv_to_grid_net_mwh:,.0f} MWh", help="Energía PV inyectada a red NETA de curtailment por concurrencia en el POI")
    c2.metric("PV → BESS", f"{hybrid.pv_to_bess_mwh:,.0f} MWh", help="Energía PV desviada a la batería (capturada del excedente + derivación intencionada). Coste de carga CERO")
    c3.metric("Curtailment", f"{hybrid.pv_curtailment_total_mwh:,.0f} MWh", help="Curtailment total estimado: recorte físico sobre el POI + residual por concurrencia PV+BESS. No se asume cero")
    c4.metric("Clipping inversor", f"{hybrid.pv_clipped_mwh:,.0f} MWh", help="Recorte DC del inversor por sobredimensionado del campo (ILR). Pérdida antes del POI")
