import streamlit as st
from bess_simulator.config import DEFAULTS, RANGES
from bess_simulator.models.parameters import (
    EconomicParams, BessParams, EfficiencyParams, ActivityParams, SimulationInputs,
    PvParams, GridParams, HybridParams, RevenueParams, RevenueModel,
)

_REVENUE_MODEL_LABELS = {
    "a) Solo arbitraje": RevenueModel.ARBITRAGE,
    "b) Arbitraje + PPA": RevenueModel.ARBITRAGE_PPA,
    "c) Arbitraje + PPA + Capacidad": RevenueModel.ARBITRAGE_PPA_CAPACITY,
    "d) Arbitraje + PPA + Capacidad + Secundaria": RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
}


def render_input_forms() -> SimulationInputs:
    st.sidebar.header("Parámetros de Simulación")

    active = st.session_state.get("active_dataset")
    site_latitude = float(DEFAULTS["pv_latitude"])
    if active is not None:
        site_latitude = float(active.get("params", {}).get("latitude", site_latitude))

    with st.sidebar.expander("Económicos", expanded=True):
        capex = st.number_input("CAPEX (€/MW)", min_value=int(RANGES["capex_per_mw"][0]), max_value=int(RANGES["capex_per_mw"][1]), value=int(DEFAULTS["capex_per_mw"]), step=10000, help="Inversión inicial por MW instalado. Incluye batería, inversor, BOS e instalación. Rango admitido: 100K-1M €/MW")
        opex = st.number_input("OPEX (€/MW/año)", min_value=int(RANGES["opex_per_mw_year"][0]), max_value=int(RANGES["opex_per_mw_year"][1]), value=int(DEFAULTS["opex_per_mw_year"]), step=500, help="Coste anual de operación y mantenimiento por MW. Incluye seguros, monitorización y mantenimiento preventivo")
        discount = st.slider("Tasa de descuento (%)", min_value=5.0, max_value=10.0, value=DEFAULTS["discount_rate"] * 100, step=0.5, help="Tasa para actualizar flujos de caja futuros. Refleja el coste de oportunidad del capital y el riesgo del proyecto") / 100
        avg_price = st.slider("Precio retribución medio (€/MWh)", min_value=20.0, max_value=100.0, value=float(DEFAULTS["avg_spread_price"]), step=1.0, help="Retribución media por MWh gestionado (diferencia entre precio de venta en descarga y compra en carga). Principal fuente de ingresos por arbitraje")

    with st.sidebar.expander("Batería BESS"):
        power = st.number_input("Potencia instalada (MW)", min_value=1, max_value=200, value=int(DEFAULTS["rated_power_mw"]), step=5, help="Capacidad nominal de potencia de la instalación BESS")
        c_rate = st.slider("1/C-Rate (MWh/MW)", min_value=1.0, max_value=8.0, value=float(DEFAULTS["c_rate_inverse"]), step=0.5, help="Horas de descarga a potencia nominal. C-Rate=4 significa 4h de descarga. Capacidad = Potencia x C-Rate MWh")
        eqo = st.number_input("Ciclos vida útil", min_value=int(RANGES["eqo_cycles"][0]), max_value=int(RANGES["eqo_cycles"][1]), value=int(DEFAULTS["eqo_cycles"]), step=100, help="Ciclos equivalentes completos garantizados por el fabricante antes de alcanzar el SoH mínimo")
        lifespan = st.slider("Vida útil (años)", min_value=10, max_value=25, value=int(DEFAULTS["lifespan_years"]), help="Horizonte temporal del análisis económico. Ember: 20 años diseño LFP, NREL: 15 años")

    with st.sidebar.expander("Eficiencia"):
        initial_soh = st.slider("SoH inicial (%)", min_value=95.0, max_value=100.0, value=DEFAULTS["initial_soh"] * 100, step=0.5, help="State of Health al inicio. 100% = batería nueva. <100% = batería con uso previo") / 100
        rte = st.slider("RTE (%)", min_value=80.0, max_value=90.0, value=DEFAULTS["rte"] * 100, step=0.5, help="Round-Trip Efficiency: energía recuperada / energía almacenada. 84% = 16% de pérdidas por ciclo") / 100
        degradation = st.select_slider("Degradación (%/ciclo)", options=[0.002, 0.003, 0.005, 0.008, 0.01], value=DEFAULTS["degradation_per_cycle"] * 100, help="Pérdida de capacidad por cada ciclo equivalente completo. Ember: 12K ciclos → 20% fade ≈ 0.0017%/ciclo") / 100
        soh_min = st.slider("SoH mínimo garantizado (%)", min_value=70.0, max_value=80.0, value=DEFAULTS["soh_min"] * 100, step=1.0, help="Umbral mínimo de State of Health aceptable. Por debajo se considera fin de vida útil") / 100
        max_dod = st.slider("DoD máximo (%)", min_value=80.0, max_value=95.0, value=DEFAULTS["max_dod"] * 100, step=1.0, help="Depth of Discharge: porcentaje máximo de descarga permitido. Mayor DoD = más energía vendida pero mayor desgaste") / 100

    with st.sidebar.expander("Actividad"):
        year_cycles = st.slider("Ciclos anuales", min_value=300, max_value=1000, value=int(DEFAULTS["year_cycles"]), step=10, help="Número de ciclos equivalentes completos previstos por año. Define la intensidad de uso de la batería")

    with st.sidebar.expander("Planta Fotovoltaica (PV)"):
        pv_peak = st.number_input("Potencia pico DC (MWp)", min_value=int(RANGES["pv_peak_power_mwp"][0]), max_value=int(RANGES["pv_peak_power_mwp"][1]), value=int(DEFAULTS["pv_peak_power_mwp"]), step=5, help="Potencia pico instalada del campo solar en corriente continua (módulos). Decisión de dimensionado del operador")
        pv_inverter = st.number_input("Potencia inversor AC (MW)", min_value=int(RANGES["pv_inverter_ac_mw"][0]), max_value=int(RANGES["pv_inverter_ac_mw"][1]), value=int(DEFAULTS["pv_inverter_ac_mw"]), step=5, help="Potencia nominal AC de los inversores PV. Limita la inyección máxima de la PV; el exceso DC se recorta (clipping)")
        pv_pr = st.slider("Performance Ratio (%)", min_value=RANGES["pv_performance_ratio"][0] * 100, max_value=RANGES["pv_performance_ratio"][1] * 100, value=DEFAULTS["pv_performance_ratio"] * 100, step=1.0, help="Rendimiento global del sistema PV frente a condiciones ideales. Incluye pérdidas de cableado, conexiones, disponibilidad") / 100
        pv_degr = st.select_slider("Degradación anual (%/año)", options=[0.2, 0.3, 0.5, 0.8, 1.0], value=DEFAULTS["pv_annual_degradation"] * 100, help="Pérdida de potencia de los módulos por año. Típico 0.5%/año en silicio cristalino") / 100
        pv_soiling = st.slider("Pérdidas por suciedad (%)", min_value=RANGES["pv_soiling_loss"][0] * 100, max_value=RANGES["pv_soiling_loss"][1] * 100, value=DEFAULTS["pv_soiling_loss"] * 100, step=0.5, help="Pérdida media anual por polvo/suciedad acumulada en los módulos entre limpiezas") / 100
        pv_capex = st.number_input("CAPEX PV (€/MWp)", min_value=int(RANGES["pv_capex_per_mwp"][0]), max_value=int(RANGES["pv_capex_per_mwp"][1]), value=int(DEFAULTS["pv_capex_per_mwp"]), step=10000, help="Inversión por MWp del campo solar. NO se incluye en el ROI de la BESS; alimenta el ROI independiente de la PV")
        pv_opex = st.number_input("OPEX PV (€/MWp/año)", min_value=int(RANGES["pv_opex_per_mwp_year"][0]), max_value=int(RANGES["pv_opex_per_mwp_year"][1]), value=int(DEFAULTS["pv_opex_per_mwp_year"]), step=500, help="Coste anual de O&M por MWp del campo solar")
        st.caption("La latitud del emplazamiento se fija en **Generación de Datos** (propiedad del sitio).")

    with st.sidebar.expander("Red / Punto de Interconexión (POI)"):
        poi_limit = st.number_input("Límite POI (MW)", min_value=int(RANGES["poi_limit_mw"][0]), max_value=int(RANGES["poi_limit_mw"][1]), value=int(DEFAULTS["poi_limit_mw"]), step=5, help="Potencia máxima de evacuación a red contratada en el punto de conexión, compartida por PV y BESS. Decisión del operador")
        curtailment_allowed = st.checkbox("Permitir curtailment", value=True, help="Si está activo, el excedente que supera el límite del POI se recorta. Si no, debe absorberse vía BESS")
        curtailment_price = st.number_input("Precio curtailment (€/MWh)", min_value=float(RANGES["curtailment_price"][0]), max_value=float(RANGES["curtailment_price"][1]), value=float(DEFAULTS["curtailment_price"]), step=1.0, help="Coste/compensación por energía recortada. 0 = pérdida total de la energía curtailada")

    with st.sidebar.expander("Estrategia Híbrida"):
        charge_priority = st.selectbox("Prioridad de carga BESS", options=["pv_first", "grid", "mixed"], index=0, help="pv_first: la BESS se carga preferentemente con excedente PV (autoconsumo del clipping). grid: carga desde red en horas baratas. mixed: combinación")
        pv_to_bess_share = st.slider("PV desviada a BESS (%)", min_value=RANGES["pv_to_bess_share"][0] * 100, max_value=RANGES["pv_to_bess_share"][1] * 100, value=DEFAULTS["pv_to_bess_share"] * 100, step=5.0, help="Fracción de la generación PV que se enruta a cargar la BESS (en lugar de inyectarla directa a red) para almacenarla y exportarla más tarde. Genera flujo PV→BESS aunque no haya excedente sobre el POI. Solo aplica con prioridad pv_first o mixed") / 100

    with st.sidebar.expander("Modelo de Negocio"):
        model_label = st.selectbox("Escenario de ingresos", options=list(_REVENUE_MODEL_LABELS.keys()), index=0, help="Streams de ingreso del BESS en capas acumulativas. Cada escenario añade una fuente sobre el anterior")
        revenue_model = _REVENUE_MODEL_LABELS[model_label]

        ppa_price = DEFAULTS["ppa_price"]
        ppa_energy_share = DEFAULTS["ppa_energy_share"]
        capacity_price = DEFAULTS["capacity_price_eur_mw_year"]
        committed_mw = DEFAULTS["committed_mw"]
        secondary_band_up_mw = DEFAULTS["secondary_band_up_mw"]
        secondary_band_down_mw = DEFAULTS["secondary_band_down_mw"]
        secondary_price = DEFAULTS["secondary_price"]
        secondary_activation_rate = DEFAULTS["secondary_activation_rate"]

        if revenue_model.has_ppa:
            ppa_price = st.slider("Precio PPA (€/MWh)", min_value=float(RANGES["ppa_price"][0]), max_value=float(RANGES["ppa_price"][1]), value=float(DEFAULTS["ppa_price"]), step=1.0, help="Precio fijo de venta contratado (Power Purchase Agreement). Aporta estabilidad de ingresos frente al arbitraje volátil")
            ppa_energy_share = st.slider("Energía bajo PPA (%)", min_value=RANGES["ppa_energy_share"][0] * 100, max_value=RANGES["ppa_energy_share"][1] * 100, value=DEFAULTS["ppa_energy_share"] * 100, step=5.0, help="Porcentaje de la energía descargada que se vende a precio PPA. El resto se vende en mercado (arbitraje)") / 100
        if revenue_model.has_capacity:
            capacity_price = st.number_input("Precio capacidad (€/MW/año)", min_value=int(RANGES["capacity_price_eur_mw_year"][0]), max_value=int(RANGES["capacity_price_eur_mw_year"][1]), value=int(DEFAULTS["capacity_price_eur_mw_year"]), step=1000, help="Pago anual por potencia firme disponible (mercado de capacidad), independiente de la energía vendida")
            committed_mw = st.number_input("Potencia comprometida (MW)", min_value=float(RANGES["committed_mw"][0]), max_value=float(RANGES["committed_mw"][1]), value=float(DEFAULTS["committed_mw"]), step=1.0, help="Potencia firme comprometida en el mercado de capacidad. Debe poder garantizarse en eventos de demanda")
        if revenue_model.has_secondary:
            secondary_band_up_mw = st.number_input("Banda a subir (MW)", min_value=float(RANGES["secondary_band_up_mw"][0]), max_value=float(RANGES["secondary_band_up_mw"][1]), value=float(DEFAULTS["secondary_band_up_mw"]), step=1.0, help="Potencia reservada para regulación secundaria a SUBIR (la BESS descarga a red si se activa). Puede diferir de la banda a bajar")
            secondary_band_down_mw = st.number_input("Banda a bajar (MW)", min_value=float(RANGES["secondary_band_down_mw"][0]), max_value=float(RANGES["secondary_band_down_mw"][1]), value=float(DEFAULTS["secondary_band_down_mw"]), step=1.0, help="Potencia reservada para regulación secundaria a BAJAR (la BESS carga desde red si se activa). Banda asimétrica respecto a la de subir si difieren")
            secondary_price = st.number_input("Precio secundaria (€/MW/h)", min_value=float(RANGES["secondary_price"][0]), max_value=float(RANGES["secondary_price"][1]), value=float(DEFAULTS["secondary_price"]), step=1.0, help="Remuneración por disponibilidad de banda de regulación secundaria (aplicada a la banda total reservada)")
            secondary_activation_rate = st.slider("Tasa de activación (%)", min_value=RANGES["secondary_activation_rate"][0] * 100, max_value=RANGES["secondary_activation_rate"][1] * 100, value=DEFAULTS["secondary_activation_rate"] * 100, step=5.0, help="Fracción de la banda que se activa realmente (energía gestionada). Consume ciclos adicionales de la BESS") / 100

    st.sidebar.divider()
    st.sidebar.subheader("Parámetros derivados")
    total_cap = power * c_rate
    total_capex = capex * power
    ilr = pv_peak / pv_inverter if pv_inverter else 0.0
    poi_util = (pv_inverter + power) / poi_limit if poi_limit else 0.0
    st.sidebar.metric("Capacidad total BESS", f"{total_cap:.0f} MWh")
    st.sidebar.metric("CAPEX total BESS", f"{total_capex:,.0f} €")
    st.sidebar.metric("OPEX total anual BESS", f"{opex * power:,.0f} €")
    st.sidebar.metric("ILR (DC/AC) PV", f"{ilr:.2f}", help="Inverter Loading Ratio = MWp(DC) / MW(AC inversor). >1 sobredimensiona el campo solar; el exceso se recorta salvo que lo capture la BESS")
    st.sidebar.metric("Utilización POI pico", f"{poi_util:.2f}", help="(AC inversor PV + AC BESS) / límite POI. >1 indica solapamiento → curtailment o desplazamiento PV→BESS")
    st.sidebar.metric("CAPEX total PV", f"{pv_capex * pv_peak:,.0f} €", help="No se incluye en el ROI de la BESS; alimenta el ROI independiente de la PV")

    return SimulationInputs(
        economic=EconomicParams(capex_per_mw=capex, opex_per_mw_year=opex, discount_rate=discount, avg_spread_price=avg_price),
        bess=BessParams(rated_power_mw=power, c_rate_inverse=c_rate, eqo_cycles=eqo, lifespan_years=lifespan),
        efficiency=EfficiencyParams(initial_soh=initial_soh, rte=rte, degradation_per_cycle=degradation, soh_min=soh_min, max_dod=max_dod),
        activity=ActivityParams(year_cycles=float(year_cycles)),
        pv=PvParams(peak_power_mwp=pv_peak, inverter_ac_mw=pv_inverter, performance_ratio=pv_pr, annual_degradation=pv_degr, soiling_loss=pv_soiling, capex_per_mwp=pv_capex, opex_per_mwp_year=pv_opex, latitude=site_latitude),
        grid=GridParams(poi_limit_mw=poi_limit, curtailment_allowed=curtailment_allowed, curtailment_price=curtailment_price),
        hybrid=HybridParams(charge_priority=charge_priority, pv_to_bess_share=pv_to_bess_share),
        revenue=RevenueParams(model=revenue_model, ppa_price=ppa_price, ppa_energy_share=ppa_energy_share, capacity_price_eur_mw_year=capacity_price, committed_mw=committed_mw, secondary_band_up_mw=secondary_band_up_mw, secondary_band_down_mw=secondary_band_down_mw, secondary_price=secondary_price, secondary_activation_rate=secondary_activation_rate),
    )
