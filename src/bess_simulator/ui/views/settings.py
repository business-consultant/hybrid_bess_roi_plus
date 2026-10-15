import streamlit as st

from bess_simulator.i18n import get_lang, t
from bess_simulator.storage.app_config import (
    DEFAULT_ADVANCED_CONFIG,
    load_config,
    reset_config,
    save_config,
)
from bess_simulator.storage.paths import get_db_path
from bess_simulator.ui.components.sticky_header import render_sticky_header

MONTH_NAMES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MONTH_NAMES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def render_settings_page():
    render_sticky_header("Configuración Avanzada")

    st.caption(
        t(
            "Parámetros internos del modelo que afectan la simulación y generación de datos sintéticos. "
            "Los cambios se guardan en base de datos y persisten entre sesiones.",
            "Internal model parameters that affect the simulation and synthetic data generation. "
            "Changes are saved to the database and persist across sessions.",
        )
    )

    cfg = dict(st.session_state.get("app_config", DEFAULT_ADVANCED_CONFIG))

    with st.expander(t("Modelo de Degradación y Eficiencia", "Degradation and Efficiency Model"), expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            cfg["calendar_aging_rate"] = st.number_input(
                t("Degradación calendario (%/año)", "Calendar degradation (%/year)"), min_value=0.1, max_value=5.0,
                value=cfg["calendar_aging_rate"] * 100, step=0.1, format="%.1f",
                help=t("Pérdida de capacidad por envejecimiento. LFP a 25°C: 0.5-2%/año (MDPI Energies 2021)", "Capacity loss from aging. LFP at 25°C: 0.5-2%/year (MDPI Energies 2021)"),
            ) / 100
            cfg["historical_cycle_degradation"] = st.number_input(
                t("Degradación cíclica histórica (%/ciclo)", "Historical cyclic degradation (%/cycle)"), min_value=0.001, max_value=0.05,
                value=cfg["historical_cycle_degradation"] * 100, step=0.001, format="%.3f",
                help=t("Pérdida por ciclo en datos históricos. Ember: 12K ciclos → 20% fade ≈ 0.0017%/ciclo", "Loss per cycle in historical data. Ember: 12K cycles → 20% fade ≈ 0.0017%/cycle"),
            ) / 100
        with c2:
            cfg["rte_annual_decay"] = st.number_input(
                t("Decaimiento RTE (%/año)", "RTE decay (%/year)"), min_value=0.0, max_value=1.0,
                value=cfg["rte_annual_decay"] * 100, step=0.05, format="%.2f",
                help=t("Pérdida anual de eficiencia. Ember: 'relativamente estable'. 0.1%/año es conservador", "Annual efficiency loss. Ember: 'relatively stable'. 0.1%/year is conservative"),
            ) / 100
            cfg["rte_base_historical"] = st.slider(
                t("RTE base histórico (%)", "Historical base RTE (%)"), min_value=80.0, max_value=95.0,
                value=cfg["rte_base_historical"] * 100, step=0.5,
                help=t("RTE inicial de los datos históricos sintéticos. NREL ATB 2024: 85%", "Initial RTE of the synthetic historical data. NREL ATB 2024: 85%"),
            ) / 100

    with st.expander(t("Modelo de Precios OMIE", "OMIE Price Model")):
        st.markdown(t("##### Curva diaria", "##### Daily curve"))
        p1, p2 = st.columns(2)
        with p1:
            cfg["omie_base_price"] = st.number_input(
                t("Precio base (€/MWh)", "Base price (€/MWh)"), min_value=20.0, max_value=120.0,
                value=float(cfg["omie_base_price"]), step=5.0,
                help=t("Nivel medio de la curva diaria. OMIE 2022-2024: ~55-65 €/MWh", "Average level of the daily curve. OMIE 2022-2024: ~55-65 €/MWh"),
            )
            cfg["omie_valley_amplitude"] = st.number_input(
                t("Amplitud valle nocturno (€/MWh)", "Overnight valley amplitude (€/MWh)"), min_value=-30.0, max_value=0.0,
                value=float(cfg["omie_valley_amplitude"]), step=1.0,
                help=t("Caída de precio en madrugada (04:00). Negativo = baja el precio", "Price drop in the early morning (04:00). Negative = lowers the price"),
            )
            cfg["omie_morning_peak_amplitude"] = st.number_input(
                t("Amplitud pico mañana (€/MWh)", "Morning peak amplitude (€/MWh)"), min_value=0.0, max_value=60.0,
                value=float(cfg["omie_morning_peak_amplitude"]), step=1.0,
                help=t("Subida de precio en pico matutino (09:00)", "Price rise at the morning peak (09:00)"),
            )
        with p2:
            cfg["omie_solar_dip_amplitude"] = st.number_input(
                t("Amplitud caída solar (€/MWh)", "Solar dip amplitude (€/MWh)"), min_value=-40.0, max_value=0.0,
                value=float(cfg["omie_solar_dip_amplitude"]), step=1.0,
                help=t("Caída por inyección solar (13:30). Negativo = baja el precio", "Drop from solar injection (13:30). Negative = lowers the price"),
            )
            cfg["omie_evening_peak_amplitude"] = st.number_input(
                t("Amplitud pico tarde (€/MWh)", "Evening peak amplitude (€/MWh)"), min_value=0.0, max_value=80.0,
                value=float(cfg["omie_evening_peak_amplitude"]), step=1.0,
                help=t("Subida de precio en pico vespertino (20:00)", "Price rise at the evening peak (20:00)"),
            )

        st.markdown(t("##### Factores semanales", "##### Weekly factors"))
        w1, w2 = st.columns(2)
        with w1:
            cfg["omie_saturday_factor"] = st.slider(
                t("Factor sábado", "Saturday factor"), min_value=0.50, max_value=1.00,
                value=float(cfg["omie_saturday_factor"]), step=0.01,
                help=t("Multiplicador de precio para sábados. 0.82 = -18%", "Price multiplier for Saturdays. 0.82 = -18%"),
            )
        with w2:
            cfg["omie_sunday_factor"] = st.slider(
                t("Factor domingo", "Sunday factor"), min_value=0.50, max_value=1.00,
                value=float(cfg["omie_sunday_factor"]), step=0.01,
                help=t("Multiplicador de precio para domingos. 0.78 = -22%", "Price multiplier for Sundays. 0.78 = -22%"),
            )

        st.markdown(t("##### Factores estacionales", "##### Seasonal factors"))
        seasonal = list(cfg["omie_seasonal_factors"])
        cols = st.columns(6)
        month_names = MONTH_NAMES_EN if get_lang() == "en" else MONTH_NAMES
        for i in range(12):
            with cols[i % 6]:
                seasonal[i] = st.number_input(
                    month_names[i], min_value=0.50, max_value=1.50,
                    value=float(seasonal[i]), step=0.01, format="%.2f",
                    key=f"seasonal_{i}",
                )
        cfg["omie_seasonal_factors"] = seasonal

        st.markdown(t("##### Ruido y límites", "##### Noise and limits"))
        n1, n2, n3, n4 = st.columns(4)
        with n1:
            cfg["omie_daily_noise_std"] = st.number_input(
                t("Ruido diario (σ €/MWh)", "Daily noise (σ €/MWh)"), min_value=0.0, max_value=20.0,
                value=float(cfg["omie_daily_noise_std"]), step=0.5,
            )
        with n2:
            cfg["omie_intraday_noise_std"] = st.number_input(
                t("Ruido intradiario (σ €/MWh)", "Intraday noise (σ €/MWh)"), min_value=0.0, max_value=10.0,
                value=float(cfg["omie_intraday_noise_std"]), step=0.5,
            )
        with n3:
            cfg["omie_price_floor"] = st.number_input(
                t("Precio mínimo (€/MWh)", "Minimum price (€/MWh)"), min_value=0.0, max_value=50.0,
                value=float(cfg["omie_price_floor"]), step=1.0,
            )
        with n4:
            cfg["omie_price_ceiling"] = st.number_input(
                t("Precio máximo (€/MWh)", "Maximum price (€/MWh)"), min_value=50.0, max_value=500.0,
                value=float(cfg["omie_price_ceiling"]), step=10.0,
            )

    with st.expander(t("Ventanas de Arbitraje y Operación", "Arbitrage and Operation Windows")):
        st.markdown(t("##### Ventanas horarias", "##### Time windows"))
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(f"**{t('Carga', 'Charge')}**")
            cfg["charge_start_hour"] = st.number_input(t("Inicio carga (h)", "Charge start (h)"), min_value=0, max_value=23, value=int(cfg["charge_start_hour"]))
            cfg["charge_end_hour"] = st.number_input(t("Fin carga (h)", "Charge end (h)"), min_value=1, max_value=24, value=int(cfg["charge_end_hour"]))
        with a2:
            st.markdown(f"**{t('Descarga AM', 'Discharge AM')}**")
            cfg["discharge_am_start_hour"] = st.number_input(t("Inicio AM (h)", "AM start (h)"), min_value=0, max_value=23, value=int(cfg["discharge_am_start_hour"]))
            cfg["discharge_am_end_hour"] = st.number_input(t("Fin AM (h)", "AM end (h)"), min_value=1, max_value=24, value=int(cfg["discharge_am_end_hour"]))
        with a3:
            st.markdown(f"**{t('Descarga PM', 'Discharge PM')}**")
            cfg["discharge_pm_start_hour"] = st.number_input(t("Inicio PM (h)", "PM start (h)"), min_value=0, max_value=23, value=int(cfg["discharge_pm_start_hour"]))
            cfg["discharge_pm_end_hour"] = st.number_input(t("Fin PM (h)", "PM end (h)"), min_value=1, max_value=24, value=int(cfg["discharge_pm_end_hour"]))

        st.markdown(t("##### Utilización", "##### Utilization"))
        u1, u2 = st.columns(2)
        with u1:
            st.markdown(f"**{t('Histórico', 'Historical')}**")
            cfg["hist_utilization_min"] = st.slider(t("Mín (%)", "Min (%)"), 50, 100, int(cfg["hist_utilization_min"] * 100), key="hu_min", help=t("Utilización mínima en ventanas de descarga históricas", "Minimum utilization in historical discharge windows")) / 100
            cfg["hist_utilization_max"] = st.slider(t("Máx (%)", "Max (%)"), 50, 100, int(cfg["hist_utilization_max"] * 100), key="hu_max") / 100
        with u2:
            st.markdown(f"**{t('Proyección', 'Forecast')}**")
            cfg["future_utilization_min"] = st.slider(t("Mín (%)", "Min (%)"), 50, 100, int(cfg["future_utilization_min"] * 100), key="fu_min") / 100
            cfg["future_utilization_max"] = st.slider(t("Máx (%)", "Max (%)"), 50, 100, int(cfg["future_utilization_max"] * 100), key="fu_max") / 100

    with st.expander(t("Umbrales de Recomendación", "Recommendation Thresholds")):
        st.caption(
            t(
                "Cortes que usa el motor de recomendaciones. Para ROI se comparan con la "
                "tasa de descuento (coste del capital). Para el resto de parámetros, el corte "
                "'ok' marca la zona óptima y el corte 'límite' la frontera del rango aconsejado: "
                "entre ambos hay margen de mejora.",
                "Cutoffs used by the recommendation engine. For ROI they are compared against "
                "the discount rate (cost of capital). For the other parameters, the 'ok' cutoff "
                "marks the optimal zone and the 'limit' cutoff the edge of the recommended range: "
                "between the two there is room for improvement.",
            )
        )
        st.markdown(t("##### ROI (rentabilidad vs. coste del capital)", "##### ROI (profitability vs. cost of capital)"))
        r1, r2 = st.columns(2)
        with r1:
            cfg["rec_roi_high_threshold"] = st.slider(
                t("Umbral ROI alto (%)", "High ROI threshold (%)"), 1.0, 20.0, cfg["rec_roi_high_threshold"] * 100, 0.5,
                help=t("ROI anualizado por encima del cual se considera rentabilidad holgada", "Annualized ROI above which profitability is considered comfortable"),
            ) / 100
        with r2:
            cfg["rec_roi_diversify_band"] = st.slider(
                t("Banda diversificación (%)", "Diversification band (%)"), 0.5, 5.0, cfg["rec_roi_diversify_band"] * 100, 0.5,
                help=t(
                    "Margen alrededor de la tasa de descuento dentro del cual el retorno se "
                    "considera 'ajustado al coste del capital' y se sugiere diversificar beneficios",
                    "Margin around the discount rate within which the return is considered "
                    "'tight to the cost of capital' and diversifying profits is suggested",
                ),
            ) / 100

        st.markdown(t("##### Tasa de descuento (€ del capital)", "##### Discount rate (cost of capital)"))
        d1, d2 = st.columns(2)
        with d1:
            cfg["rec_discount_rate_ok"] = st.slider(
                t("Tasa ok (%)", "OK rate (%)"), 4.0, 12.0, cfg["rec_discount_rate_ok"] * 100, 0.5,
                help=t("Por debajo de este valor la tasa se considera razonable (sin acción)", "Below this value the rate is considered reasonable (no action)"),
            ) / 100
        with d2:
            cfg["rec_discount_rate_warning"] = st.slider(
                t("Tasa límite (%)", "Limit rate (%)"), 6.0, 18.0, cfg["rec_discount_rate_warning"] * 100, 0.5,
                help=t("Por encima de este valor la tasa se considera en el límite del rango aconsejado", "Above this value the rate is considered at the edge of the recommended range"),
            ) / 100

        st.markdown(t("##### OPEX (€/MW/año)", "##### OPEX (€/MW/year)"))
        o1, o2 = st.columns(2)
        with o1:
            cfg["rec_opex_ok"] = st.number_input(
                t("OPEX ok (€/MW/año)", "OK OPEX (€/MW/year)"), value=int(cfg["rec_opex_ok"]), step=1000,
                help=t("Por debajo: zona óptima de coste de O&M", "Below: optimal O&M cost zone"),
            )
        with o2:
            cfg["rec_opex_warning"] = st.number_input(
                t("OPEX límite (€/MW/año)", "Limit OPEX (€/MW/year)"), value=int(cfg["rec_opex_warning"]), step=1000,
                help=t("Por encima: en el límite del rango aconsejado", "Above: at the edge of the recommended range"),
            )

        st.markdown(t("##### RTE (Round Trip Efficiency)", "##### RTE (Round Trip Efficiency)"))
        e1, e2 = st.columns(2)
        with e1:
            cfg["rec_rte_ok"] = st.slider(
                t("RTE ok (%)", "OK RTE (%)"), 80.0, 95.0, cfg["rec_rte_ok"] * 100, 1.0,
                help=t("Por encima: rendimiento de ciclo en zona óptima", "Above: round-trip efficiency in optimal zone"),
            ) / 100
        with e2:
            cfg["rec_rte_warning"] = st.slider(
                t("RTE límite (%)", "Limit RTE (%)"), 70.0, 90.0, cfg["rec_rte_warning"] * 100, 1.0,
                help=t("Por debajo: en el límite del rango aconsejado", "Below: at the edge of the recommended range"),
            ) / 100

        st.markdown(t("##### Vida útil (años)", "##### Useful life (years)"))
        l1, l2 = st.columns(2)
        with l1:
            cfg["rec_lifespan_ok"] = st.number_input(
                t("Vida útil ok (años)", "OK useful life (years)"), value=int(cfg["rec_lifespan_ok"]),
                help=t("Igual o superior: vida útil en zona óptima", "Equal or above: useful life in optimal zone"),
            )
        with l2:
            cfg["rec_lifespan_warning"] = st.number_input(
                t("Vida útil límite (años)", "Limit useful life (years)"), value=int(cfg["rec_lifespan_warning"]),
                help=t("Por debajo: en el límite del rango aconsejado", "Below: at the edge of the recommended range"),
            )

        st.markdown(t("##### Precio de retribución (€/MWh)", "##### Retribution price (€/MWh)"))
        p1, p2 = st.columns(2)
        with p1:
            cfg["rec_price_ok"] = st.number_input(
                t("Precio ok (€/MWh)", "OK price (€/MWh)"), value=float(cfg["rec_price_ok"]), step=5.0,
                help=t("Por encima: retribución de mercado en zona óptima", "Above: market retribution in optimal zone"),
            )
        with p2:
            cfg["rec_price_warning"] = st.number_input(
                t("Precio límite (€/MWh)", "Limit price (€/MWh)"), value=float(cfg["rec_price_warning"]), step=5.0,
                help=t("Por debajo: en el límite del rango aconsejado", "Below: at the edge of the recommended range"),
            )

    with st.expander(t("Alertas Históricas y Anomalías (APM)", "Historical Alerts and Anomalies (APM)")):
        st.caption(
            t(
                "Umbrales de las magnitudes críticas (seguridad, salud y garantía) "
                "que se registran como eventos al salirse de rango, y la inyección de "
                "anomalías controladas en el histórico sintético que las alimenta.",
                "Thresholds for the critical magnitudes (safety, health and warranty) "
                "that get logged as events when out of range, and the injection of "
                "controlled anomalies in the synthetic history that feeds them.",
            )
        )
        st.markdown(t("##### Umbrales de alerta", "##### Alert thresholds"))
        a1, a2, a3 = st.columns(3)
        with a1:
            cfg["alarm_temp_critical_c"] = st.number_input(
                t("Temperatura crítica (°C)", "Critical temperature (°C)"), value=float(cfg["alarm_temp_critical_c"]),
                step=1.0, help=t("Seguridad: por encima se registra sobre-temperatura", "Safety: above this, over-temperature is logged"),
            )
        with a2:
            cfg["alarm_rte_min"] = st.number_input(
                t("RTE mínimo contractual", "Minimum contractual RTE"), value=float(cfg["alarm_rte_min"]),
                min_value=0.50, max_value=0.95, step=0.01,
                help=t("Garantía: por debajo se registra caída de rendimiento", "Warranty: below this, a performance drop is logged"),
            )
        with a3:
            cfg["alarm_soh_min"] = st.number_input(
                t("SoH mínimo garantizado", "Minimum guaranteed SoH"), value=float(cfg["alarm_soh_min"]),
                min_value=0.50, max_value=1.0, step=0.01,
                help=t("Salud: por debajo se registra pérdida de capacidad", "Health: below this, capacity loss is logged"),
            )

        st.markdown(t("##### Semáforo de garantía (vista de elementos)", "##### Warranty semaphore (elements view)"))
        st.caption(
            t(
                "Límites contractuales que colorean las tarjetas de *warranty "
                "compliance* del detalle BESS. El suelo de SoH y la temperatura "
                "crítica se toman de los umbrales de alerta de arriba.",
                "Contractual limits that color the *warranty compliance* cards in "
                "the BESS detail. The SoH floor and critical temperature are taken "
                "from the alert thresholds above.",
            )
        )
        w1, w2, w3 = st.columns(3)
        with w1:
            cfg["warranty_soh_spread_max_pp"] = st.number_input(
                t("SoH spread máx. (pp)", "Max SoH spread (pp)"),
                value=float(cfg["warranty_soh_spread_max_pp"]),
                min_value=1.0, step=0.5,
                help=t("Dispersión máx. de SoH admisible en el grupo", "Maximum admissible SoH spread within the group"),
            )
        with w2:
            cfg["warranty_cycles_max"] = st.number_input(
                t("Ciclos equiv. tope", "Max equiv. cycles"),
                value=float(cfg["warranty_cycles_max"]),
                min_value=500.0, step=250.0,
                help=t("Tope contractual de ciclos equivalentes", "Contractual cap on equivalent cycles"),
            )
        with w3:
            cfg["warranty_dod_max_pct"] = st.number_input(
                t("DoD máx. (%)", "Max DoD (%)"),
                value=float(cfg["warranty_dod_max_pct"]),
                min_value=50.0, max_value=100.0, step=1.0,
                help=t("Profundidad de descarga máx. admisible por ciclo", "Maximum admissible depth of discharge per cycle"),
            )

        st.markdown(t("##### Inyección de anomalías (histórico sintético)", "##### Anomaly injection (synthetic history)"))
        cfg["anomaly_enable"] = st.checkbox(
            t("Inyectar anomalías controladas", "Inject controlled anomalies"), value=bool(cfg["anomaly_enable"]),
            help=t("Genera episodios puntuales fuera de rango para alimentar el registro", "Generates occasional out-of-range episodes to feed the log"),
        )
        an1, an2 = st.columns(2)
        with an1:
            cfg["anomaly_temp_events_per_year"] = st.number_input(
                t("Episodios de temperatura/año", "Temperature episodes/year"),
                value=float(cfg["anomaly_temp_events_per_year"]), min_value=0.0, step=1.0,
            )
            cfg["anomaly_temp_peak_c"] = st.number_input(
                t("Pico de temperatura (°C)", "Temperature peak (°C)"),
                value=float(cfg["anomaly_temp_peak_c"]), step=1.0,
            )
        with an2:
            cfg["anomaly_rte_events_per_year"] = st.number_input(
                t("Episodios de RTE/año", "RTE episodes/year"),
                value=float(cfg["anomaly_rte_events_per_year"]), min_value=0.0, step=1.0,
            )
            cfg["anomaly_rte_dip"] = st.number_input(
                t("RTE en la caída", "RTE at the dip"), value=float(cfg["anomaly_rte_dip"]),
                min_value=0.40, max_value=0.90, step=0.01,
            )

    st.divider()
    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button(t("Guardar configuración", "Save settings"), type="primary", use_container_width=True):
            save_config(get_db_path(), cfg)
            st.session_state["app_config"] = cfg
            st.success(t("Configuración guardada", "Settings saved"))
    with col_reset:
        if st.button(t("Restaurar valores por defecto", "Restore default values"), type="secondary", use_container_width=True):
            reset_config(get_db_path())
            st.session_state["app_config"] = dict(DEFAULT_ADVANCED_CONFIG)
            st.success(t("Valores restaurados", "Values restored"))
            st.rerun()
