import streamlit as st

from bess_simulator.i18n import t
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

    with st.expander(t("Más resultados", "More results"), expanded=False):
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
            delta_text, delta_color = t("Rentable", "Profitable"), "normal"
        elif roi > 0:
            delta_text, delta_color = t("Rentabilidad baja", "Low profitability"), "off"
        else:
            delta_text, delta_color = t("No rentable", "Not profitable"), "inverse"
        st.metric(t("ROI (anualizado)", "ROI (annualized)"), f"{roi:.2%}", delta=delta_text, delta_color=delta_color)
        st.caption(t(f"Retorno anualizado sobre inversión. > tasa descuento ({discount_rate:.0%}) = rentable", f"Annualized return on investment. > discount rate ({discount_rate:.0%}) = profitable"))

    with col2:
        van_color = "normal" if van >= 0 else "inverse"
        st.metric(t("VAN (NPV)", "NPV"), f"{van:,.0f} €", delta=t("Positivo", "Positive") if van >= 0 else t("Negativo", "Negative"), delta_color=van_color)
        st.caption(t("Valor Actual Neto: suma de flujos de caja descontados − CAPEX. > 0 = genera valor", "Net Present Value: sum of discounted cash flows − CAPEX. > 0 = creates value"))


def render_hybrid_kpis(
    bess_roi: float,
    bess_van: float,
    hybrid: HybridEconomics,
    discount_rate: float = 0.06,
):
    """KPIs de planta híbrida: ROI BESS y ROI PV por separado.

    El ROI de la BESS y el de la PV son independientes (no comparten CAPEX).
    """
    st.markdown(t("#### Rentabilidad por activo (BESS vs PV)", "#### Profitability by asset (BESS vs PV)"))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(t("ROI BESS (anualizado)", "BESS ROI (annualized)"), f"{bess_roi:.2%}")
        st.caption(t("Solo CAPEX/OPEX de la batería. No incluye la inversión PV", "Battery CAPEX/OPEX only. Does not include the PV investment"))
    with c2:
        st.metric(t("ROI PV (anualizado)", "PV ROI (annualized)"), f"{hybrid.pv_roi:.2%}")
        st.caption(t("Economía independiente del campo solar (CAPEX/OPEX PV)", "Independent economics of the solar field (PV CAPEX/OPEX)"))
    with c3:
        plant_van = bess_van + hybrid.pv_van + hybrid.synergy_pv_charge_credit
        van_color = "normal" if plant_van >= 0 else "inverse"
        st.metric(t("VAN planta (BESS + PV)", "Plant NPV (BESS + PV)"), f"{plant_van:,.0f} €", delta_color=van_color)
        st.caption(t("VAN BESS + VAN PV + crédito de sinergia PV→BESS", "BESS NPV + PV NPV + PV→BESS synergy credit"))


def render_hybrid_synergy(hybrid: HybridEconomics):
    """Reconciliación energética PV↔BESS: carga solar, spread efectivo, curtailment.

    Cierra la fisura de valor: la energía PV→BESS se asigna a coste CERO y el
    ahorro de carga de red se reconoce como crédito de sinergia (vitamina el
    spread del BESS). El curtailment se estima (no se asume cero) y su coste
    ajusta la producción PV vendible.
    """
    st.markdown(t("#### Reconciliación PV↔BESS (sinergia y curtailment)", "#### PV↔BESS reconciliation (synergy and curtailment)"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        t("Carga BESS de origen solar", "Solar-sourced BESS charging"),
        f"{hybrid.bess_solar_fraction:.1%}",
        help=t(
            f"f_PV: fracción de la demanda anual de carga de la BESS cubierta por "
            f"la PV a coste cero. Carga solar: {hybrid.bess_solar_charge_mwh:,.0f} MWh "
            f"sobre {hybrid.bess_charge_demand_mwh:,.0f} MWh de demanda de carga",
            f"f_PV: fraction of the BESS's annual charging demand covered by PV "
            f"at zero cost. Solar charge: {hybrid.bess_solar_charge_mwh:,.0f} MWh "
            f"out of {hybrid.bess_charge_demand_mwh:,.0f} MWh of charging demand",
        ),
    )
    c2.metric(
        t("Spread efectivo", "Effective spread"),
        f"{hybrid.bess_effective_spread:,.1f} €/MWh",
        delta=f"+{hybrid.bess_effective_spread - hybrid.bess_base_spread:,.1f} {t('vs base', 'vs base')}",
        delta_color="normal",
        help=t("Spread base vitaminado por la carga solar gratuita (ahorro de compra en pool)", "Base spread boosted by free solar charging (avoided pool purchase cost)"),
    )
    c3.metric(
        t("Crédito de sinergia PV→BESS", "PV→BESS synergy credit"),
        f"{hybrid.synergy_pv_charge_credit:,.0f} €",
        help=t("Ahorro de vida útil (descontado) por cargar la BESS con PV en lugar de comprar en pool", "Lifetime savings (discounted) from charging the BESS with PV instead of buying in the pool"),
    )
    c4.metric(
        t("Coste del curtailment", "Curtailment cost"),
        f"{hybrid.pv_curtailment_cost_total:,.0f} €",
        delta_color="off",
        help=t(
            f"Ingreso PV perdido (vida útil) por el curtailment estimado: "
            f"{hybrid.pv_curtailment_total_mwh:,.0f} MWh/año "
            f"({hybrid.pv_curtailed_concurrency_mwh:,.0f} por concurrencia POI)",
            f"PV revenue lost (lifetime) from the estimated curtailment: "
            f"{hybrid.pv_curtailment_total_mwh:,.0f} MWh/year "
            f"({hybrid.pv_curtailed_concurrency_mwh:,.0f} from POI concurrency)",
        ),
    )


def render_revenue_breakdown(breakdown: RevenueBreakdown):
    """Desglose de los ingresos del BESS por stream (a/b/c/d)."""
    total = breakdown.total
    if total <= 0:
        return
    st.markdown(t("#### Ingresos BESS por stream (vida útil)", "#### BESS revenue by stream (lifetime)"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Arbitraje", "Arbitrage"), f"{breakdown.arbitrage:,.0f} €", delta=f"{breakdown.arbitrage / total:.0%}", delta_color="off")
    c2.metric("PPA", f"{breakdown.ppa:,.0f} €", delta=f"{breakdown.ppa / total:.0%}", delta_color="off")
    c3.metric(t("Capacidad", "Capacity"), f"{breakdown.capacity:,.0f} €", delta=f"{breakdown.capacity / total:.0%}", delta_color="off")
    c4.metric(t("Secundaria", "Secondary"), f"{breakdown.secondary:,.0f} €", delta=f"{breakdown.secondary / total:.0%}", delta_color="off")


def render_hybrid_flows(hybrid: HybridEconomics):
    """Flujos de energía en el POI (año representativo)."""
    st.markdown(t("#### Flujos híbridos en el POI (año representativo)", "#### Hybrid flows at the POI (representative year)"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("PV → red (neto)", "PV → grid (net)"), f"{hybrid.pv_to_grid_net_mwh:,.0f} MWh", help=t("Energía PV inyectada a red NETA de curtailment por concurrencia en el POI", "PV energy injected to the grid NET of concurrency curtailment at the POI"))
    c2.metric("PV → BESS", f"{hybrid.pv_to_bess_mwh:,.0f} MWh", help=t("Energía PV desviada a la batería (capturada del excedente + derivación intencionada). Coste de carga CERO", "PV energy diverted to the battery (captured surplus + intentional diversion). ZERO charging cost"))
    c3.metric(t("Curtailment", "Curtailment"), f"{hybrid.pv_curtailment_total_mwh:,.0f} MWh", help=t("Curtailment total estimado: recorte físico sobre el POI + residual por concurrencia PV+BESS. No se asume cero", "Total estimated curtailment: physical clipping at the POI + residual from PV+BESS concurrency. Not assumed to be zero"))
    c4.metric(t("Clipping inversor", "Inverter clipping"), f"{hybrid.pv_clipped_mwh:,.0f} MWh", help=t("Recorte DC del inversor por sobredimensionado del campo (ILR). Pérdida antes del POI", "Inverter DC clipping from field oversizing (ILR). Loss before the POI"))
