import streamlit as st

from bess_simulator.storage.app_config import (
    DEFAULT_ADVANCED_CONFIG,
    load_config,
    reset_config,
    save_config,
)
from bess_simulator.storage.paths import get_db_path
from bess_simulator.ui.components.sticky_header import render_sticky_header

MONTH_NAMES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def render_settings_page():
    render_sticky_header("Configuración Avanzada")

    st.caption(
        "Parámetros internos del modelo que afectan la simulación y generación de datos sintéticos. "
        "Los cambios se guardan en base de datos y persisten entre sesiones."
    )

    cfg = dict(st.session_state.get("app_config", DEFAULT_ADVANCED_CONFIG))

    with st.expander("Modelo de Degradación y Eficiencia", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            cfg["calendar_aging_rate"] = st.number_input(
                "Degradación calendario (%/año)", min_value=0.1, max_value=5.0,
                value=cfg["calendar_aging_rate"] * 100, step=0.1, format="%.1f",
                help="Pérdida de capacidad por envejecimiento. LFP a 25°C: 0.5-2%/año (MDPI Energies 2021)",
            ) / 100
            cfg["historical_cycle_degradation"] = st.number_input(
                "Degradación cíclica histórica (%/ciclo)", min_value=0.001, max_value=0.05,
                value=cfg["historical_cycle_degradation"] * 100, step=0.001, format="%.3f",
                help="Pérdida por ciclo en datos históricos. Ember: 12K ciclos → 20% fade ≈ 0.0017%/ciclo",
            ) / 100
        with c2:
            cfg["rte_annual_decay"] = st.number_input(
                "Decaimiento RTE (%/año)", min_value=0.0, max_value=1.0,
                value=cfg["rte_annual_decay"] * 100, step=0.05, format="%.2f",
                help="Pérdida anual de eficiencia. Ember: 'relativamente estable'. 0.1%/año es conservador",
            ) / 100
            cfg["rte_base_historical"] = st.slider(
                "RTE base histórico (%)", min_value=80.0, max_value=95.0,
                value=cfg["rte_base_historical"] * 100, step=0.5,
                help="RTE inicial de los datos históricos sintéticos. NREL ATB 2024: 85%",
            ) / 100

    with st.expander("Modelo de Precios OMIE"):
        st.markdown("##### Curva diaria")
        p1, p2 = st.columns(2)
        with p1:
            cfg["omie_base_price"] = st.number_input(
                "Precio base (€/MWh)", min_value=20.0, max_value=120.0,
                value=float(cfg["omie_base_price"]), step=5.0,
                help="Nivel medio de la curva diaria. OMIE 2022-2024: ~55-65 €/MWh",
            )
            cfg["omie_valley_amplitude"] = st.number_input(
                "Amplitud valle nocturno (€/MWh)", min_value=-30.0, max_value=0.0,
                value=float(cfg["omie_valley_amplitude"]), step=1.0,
                help="Caída de precio en madrugada (04:00). Negativo = baja el precio",
            )
            cfg["omie_morning_peak_amplitude"] = st.number_input(
                "Amplitud pico mañana (€/MWh)", min_value=0.0, max_value=60.0,
                value=float(cfg["omie_morning_peak_amplitude"]), step=1.0,
                help="Subida de precio en pico matutino (09:00)",
            )
        with p2:
            cfg["omie_solar_dip_amplitude"] = st.number_input(
                "Amplitud caída solar (€/MWh)", min_value=-40.0, max_value=0.0,
                value=float(cfg["omie_solar_dip_amplitude"]), step=1.0,
                help="Caída por inyección solar (13:30). Negativo = baja el precio",
            )
            cfg["omie_evening_peak_amplitude"] = st.number_input(
                "Amplitud pico tarde (€/MWh)", min_value=0.0, max_value=80.0,
                value=float(cfg["omie_evening_peak_amplitude"]), step=1.0,
                help="Subida de precio en pico vespertino (20:00)",
            )

        st.markdown("##### Factores semanales")
        w1, w2 = st.columns(2)
        with w1:
            cfg["omie_saturday_factor"] = st.slider(
                "Factor sábado", min_value=0.50, max_value=1.00,
                value=float(cfg["omie_saturday_factor"]), step=0.01,
                help="Multiplicador de precio para sábados. 0.82 = -18%",
            )
        with w2:
            cfg["omie_sunday_factor"] = st.slider(
                "Factor domingo", min_value=0.50, max_value=1.00,
                value=float(cfg["omie_sunday_factor"]), step=0.01,
                help="Multiplicador de precio para domingos. 0.78 = -22%",
            )

        st.markdown("##### Factores estacionales")
        seasonal = list(cfg["omie_seasonal_factors"])
        cols = st.columns(6)
        for i in range(12):
            with cols[i % 6]:
                seasonal[i] = st.number_input(
                    MONTH_NAMES[i], min_value=0.50, max_value=1.50,
                    value=float(seasonal[i]), step=0.01, format="%.2f",
                    key=f"seasonal_{i}",
                )
        cfg["omie_seasonal_factors"] = seasonal

        st.markdown("##### Ruido y límites")
        n1, n2, n3, n4 = st.columns(4)
        with n1:
            cfg["omie_daily_noise_std"] = st.number_input(
                "Ruido diario (σ €/MWh)", min_value=0.0, max_value=20.0,
                value=float(cfg["omie_daily_noise_std"]), step=0.5,
            )
        with n2:
            cfg["omie_intraday_noise_std"] = st.number_input(
                "Ruido intradiario (σ €/MWh)", min_value=0.0, max_value=10.0,
                value=float(cfg["omie_intraday_noise_std"]), step=0.5,
            )
        with n3:
            cfg["omie_price_floor"] = st.number_input(
                "Precio mínimo (€/MWh)", min_value=0.0, max_value=50.0,
                value=float(cfg["omie_price_floor"]), step=1.0,
            )
        with n4:
            cfg["omie_price_ceiling"] = st.number_input(
                "Precio máximo (€/MWh)", min_value=50.0, max_value=500.0,
                value=float(cfg["omie_price_ceiling"]), step=10.0,
            )

    with st.expander("Ventanas de Arbitraje y Operación"):
        st.markdown("##### Ventanas horarias")
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown("**Carga**")
            cfg["charge_start_hour"] = st.number_input("Inicio carga (h)", min_value=0, max_value=23, value=int(cfg["charge_start_hour"]))
            cfg["charge_end_hour"] = st.number_input("Fin carga (h)", min_value=1, max_value=24, value=int(cfg["charge_end_hour"]))
        with a2:
            st.markdown("**Descarga AM**")
            cfg["discharge_am_start_hour"] = st.number_input("Inicio AM (h)", min_value=0, max_value=23, value=int(cfg["discharge_am_start_hour"]))
            cfg["discharge_am_end_hour"] = st.number_input("Fin AM (h)", min_value=1, max_value=24, value=int(cfg["discharge_am_end_hour"]))
        with a3:
            st.markdown("**Descarga PM**")
            cfg["discharge_pm_start_hour"] = st.number_input("Inicio PM (h)", min_value=0, max_value=23, value=int(cfg["discharge_pm_start_hour"]))
            cfg["discharge_pm_end_hour"] = st.number_input("Fin PM (h)", min_value=1, max_value=24, value=int(cfg["discharge_pm_end_hour"]))

        st.markdown("##### Utilización")
        u1, u2 = st.columns(2)
        with u1:
            st.markdown("**Histórico**")
            cfg["hist_utilization_min"] = st.slider("Mín (%)", 50, 100, int(cfg["hist_utilization_min"] * 100), key="hu_min", help="Utilización mínima en ventanas de descarga históricas") / 100
            cfg["hist_utilization_max"] = st.slider("Máx (%)", 50, 100, int(cfg["hist_utilization_max"] * 100), key="hu_max") / 100
        with u2:
            st.markdown("**Proyección**")
            cfg["future_utilization_min"] = st.slider("Mín (%)", 50, 100, int(cfg["future_utilization_min"] * 100), key="fu_min") / 100
            cfg["future_utilization_max"] = st.slider("Máx (%)", 50, 100, int(cfg["future_utilization_max"] * 100), key="fu_max") / 100

    with st.expander("Umbrales de Recomendación"):
        st.caption(
            "Cortes que usa el motor de recomendaciones. Para ROI se comparan con la "
            "tasa de descuento (coste del capital). Para el resto de parámetros, el corte "
            "'ok' marca la zona óptima y el corte 'límite' la frontera del rango aconsejado: "
            "entre ambos hay margen de mejora."
        )
        st.markdown("##### ROI (rentabilidad vs. coste del capital)")
        r1, r2 = st.columns(2)
        with r1:
            cfg["rec_roi_high_threshold"] = st.slider(
                "Umbral ROI alto (%)", 1.0, 20.0, cfg["rec_roi_high_threshold"] * 100, 0.5,
                help="ROI anualizado por encima del cual se considera rentabilidad holgada",
            ) / 100
        with r2:
            cfg["rec_roi_diversify_band"] = st.slider(
                "Banda diversificación (%)", 0.5, 5.0, cfg["rec_roi_diversify_band"] * 100, 0.5,
                help="Margen alrededor de la tasa de descuento dentro del cual el retorno se "
                     "considera 'ajustado al coste del capital' y se sugiere diversificar beneficios",
            ) / 100

        st.markdown("##### Tasa de descuento (€ del capital)")
        d1, d2 = st.columns(2)
        with d1:
            cfg["rec_discount_rate_ok"] = st.slider(
                "Tasa ok (%)", 4.0, 12.0, cfg["rec_discount_rate_ok"] * 100, 0.5,
                help="Por debajo de este valor la tasa se considera razonable (sin acción)",
            ) / 100
        with d2:
            cfg["rec_discount_rate_warning"] = st.slider(
                "Tasa límite (%)", 6.0, 18.0, cfg["rec_discount_rate_warning"] * 100, 0.5,
                help="Por encima de este valor la tasa se considera en el límite del rango aconsejado",
            ) / 100

        st.markdown("##### OPEX (€/MW/año)")
        o1, o2 = st.columns(2)
        with o1:
            cfg["rec_opex_ok"] = st.number_input(
                "OPEX ok (€/MW/año)", value=int(cfg["rec_opex_ok"]), step=1000,
                help="Por debajo: zona óptima de coste de O&M",
            )
        with o2:
            cfg["rec_opex_warning"] = st.number_input(
                "OPEX límite (€/MW/año)", value=int(cfg["rec_opex_warning"]), step=1000,
                help="Por encima: en el límite del rango aconsejado",
            )

        st.markdown("##### RTE (Round Trip Efficiency)")
        e1, e2 = st.columns(2)
        with e1:
            cfg["rec_rte_ok"] = st.slider(
                "RTE ok (%)", 80.0, 95.0, cfg["rec_rte_ok"] * 100, 1.0,
                help="Por encima: rendimiento de ciclo en zona óptima",
            ) / 100
        with e2:
            cfg["rec_rte_warning"] = st.slider(
                "RTE límite (%)", 70.0, 90.0, cfg["rec_rte_warning"] * 100, 1.0,
                help="Por debajo: en el límite del rango aconsejado",
            ) / 100

        st.markdown("##### Vida útil (años)")
        l1, l2 = st.columns(2)
        with l1:
            cfg["rec_lifespan_ok"] = st.number_input(
                "Vida útil ok (años)", value=int(cfg["rec_lifespan_ok"]),
                help="Igual o superior: vida útil en zona óptima",
            )
        with l2:
            cfg["rec_lifespan_warning"] = st.number_input(
                "Vida útil límite (años)", value=int(cfg["rec_lifespan_warning"]),
                help="Por debajo: en el límite del rango aconsejado",
            )

        st.markdown("##### Precio de retribución (€/MWh)")
        p1, p2 = st.columns(2)
        with p1:
            cfg["rec_price_ok"] = st.number_input(
                "Precio ok (€/MWh)", value=float(cfg["rec_price_ok"]), step=5.0,
                help="Por encima: retribución de mercado en zona óptima",
            )
        with p2:
            cfg["rec_price_warning"] = st.number_input(
                "Precio límite (€/MWh)", value=float(cfg["rec_price_warning"]), step=5.0,
                help="Por debajo: en el límite del rango aconsejado",
            )

    with st.expander("Alertas Históricas y Anomalías (APM)"):
        st.caption(
            "Umbrales de las magnitudes críticas (seguridad, salud y garantía) "
            "que se registran como eventos al salirse de rango, y la inyección de "
            "anomalías controladas en el histórico sintético que las alimenta."
        )
        st.markdown("##### Umbrales de alerta")
        a1, a2, a3 = st.columns(3)
        with a1:
            cfg["alarm_temp_critical_c"] = st.number_input(
                "Temperatura crítica (°C)", value=float(cfg["alarm_temp_critical_c"]),
                step=1.0, help="Seguridad: por encima se registra sobre-temperatura",
            )
        with a2:
            cfg["alarm_rte_min"] = st.number_input(
                "RTE mínimo contractual", value=float(cfg["alarm_rte_min"]),
                min_value=0.50, max_value=0.95, step=0.01,
                help="Garantía: por debajo se registra caída de rendimiento",
            )
        with a3:
            cfg["alarm_soh_min"] = st.number_input(
                "SoH mínimo garantizado", value=float(cfg["alarm_soh_min"]),
                min_value=0.50, max_value=1.0, step=0.01,
                help="Salud: por debajo se registra pérdida de capacidad",
            )

        st.markdown("##### Semáforo de garantía (vista de elementos)")
        st.caption(
            "Límites contractuales que colorean las tarjetas de *warranty "
            "compliance* del detalle BESS. El suelo de SoH y la temperatura "
            "crítica se toman de los umbrales de alerta de arriba."
        )
        w1, w2, w3 = st.columns(3)
        with w1:
            cfg["warranty_soh_spread_max_pp"] = st.number_input(
                "SoH spread máx. (pp)",
                value=float(cfg["warranty_soh_spread_max_pp"]),
                min_value=1.0, step=0.5,
                help="Dispersión máx. de SoH admisible en el grupo",
            )
        with w2:
            cfg["warranty_cycles_max"] = st.number_input(
                "Ciclos equiv. tope",
                value=float(cfg["warranty_cycles_max"]),
                min_value=500.0, step=250.0,
                help="Tope contractual de ciclos equivalentes",
            )
        with w3:
            cfg["warranty_dod_max_pct"] = st.number_input(
                "DoD máx. (%)",
                value=float(cfg["warranty_dod_max_pct"]),
                min_value=50.0, max_value=100.0, step=1.0,
                help="Profundidad de descarga máx. admisible por ciclo",
            )

        st.markdown("##### Inyección de anomalías (histórico sintético)")
        cfg["anomaly_enable"] = st.checkbox(
            "Inyectar anomalías controladas", value=bool(cfg["anomaly_enable"]),
            help="Genera episodios puntuales fuera de rango para alimentar el registro",
        )
        an1, an2 = st.columns(2)
        with an1:
            cfg["anomaly_temp_events_per_year"] = st.number_input(
                "Episodios de temperatura/año",
                value=float(cfg["anomaly_temp_events_per_year"]), min_value=0.0, step=1.0,
            )
            cfg["anomaly_temp_peak_c"] = st.number_input(
                "Pico de temperatura (°C)",
                value=float(cfg["anomaly_temp_peak_c"]), step=1.0,
            )
        with an2:
            cfg["anomaly_rte_events_per_year"] = st.number_input(
                "Episodios de RTE/año",
                value=float(cfg["anomaly_rte_events_per_year"]), min_value=0.0, step=1.0,
            )
            cfg["anomaly_rte_dip"] = st.number_input(
                "RTE en la caída", value=float(cfg["anomaly_rte_dip"]),
                min_value=0.40, max_value=0.90, step=0.01,
            )

    st.divider()
    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("Guardar configuración", type="primary", use_container_width=True):
            save_config(get_db_path(), cfg)
            st.session_state["app_config"] = cfg
            st.success("Configuración guardada")
    with col_reset:
        if st.button("Restaurar valores por defecto", type="secondary", use_container_width=True):
            reset_config(get_db_path())
            st.session_state["app_config"] = dict(DEFAULT_ADVANCED_CONFIG)
            st.success("Valores restaurados")
            st.rerun()
