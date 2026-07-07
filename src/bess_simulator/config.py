# ---------------------------------------------------------------------------
# Referencias para rangos y valores por defecto
# ---------------------------------------------------------------------------
# CAPEX: 100K-1M €/MW — cubre mercado europeo (Ember 2025: ~€120/kWh → ~€480K/MW 4h)
# OPEX: 10K-22.5K €/MW/año — NREL ATB 2024 (2.5% CAPEX), Ember (2% CAPEX)
# RTE: 80-90% — NREL ATB 2024 (85%), Ember 2025 (90% AC-AC)
# Vida útil: 10-25 años — NREL ATB 2024 (15 años), Ember (20 años diseño)
# Ciclos: 6K-12K — Ember (10K-12K garantizados para LFP)
# Degradación cíclica: 0.002-0.005%/ciclo — Ember (12K ciclos → 20% fade ≈ 0.0017%/ciclo)
# Degradación calendario: ~1.5%/año — MDPI Energies 2021, conservador para 25°C + SOC operativo
# RTE decay: ~0.1%/año absoluto — Ember: "relatively stable", Anern: "decreases slightly"
# Spread: 20-100 €/MWh — cubre rango OMIE/Synertics (25-67 €/MWh obs. 2021-2023)
# ---------------------------------------------------------------------------

INTERVALS_PER_HOUR: int = 4       # 15-minute resolution
INTERVALS_PER_DAY: int = 96       # 24 * 4
INTERVAL_DURATION_H: float = 0.25  # hours per interval


RANGES: dict[str, tuple[float, float]] = {
    "capex_per_mw": (100_000, 1_000_000),
    "opex_per_mw_year": (8_000, 22_500),
    "discount_rate": (0.05, 0.10),
    "avg_spread_price": (20, 100),
    "rated_power_mw": (1, 200),
    "c_rate_inverse": (1, 8),
    "eqo_cycles": (6_000, 8_000),
    "lifespan_years": (10, 25),
    "initial_soh": (0.95, 1.0),
    "rte": (0.80, 0.90),
    "degradation_per_cycle": (0.00002, 0.0001),
    "soh_min": (0.70, 0.80),
    "max_dod": (0.80, 0.95),
    "min_soc": (0.05, 0.20),
    "year_cycles": (300, 1000),
    # --- Planta fotovoltaica (PV) hibridada ---
    "pv_peak_power_mwp": (1, 400),
    "pv_inverter_ac_mw": (1, 300),
    "pv_performance_ratio": (0.70, 0.90),
    "pv_annual_degradation": (0.002, 0.010),
    "pv_soiling_loss": (0.0, 0.10),
    "pv_capex_per_mwp": (350_000, 900_000),
    "pv_opex_per_mwp_year": (6_000, 20_000),
    "pv_latitude": (-60, 60),
    # --- Punto de interconexión (POI) / red ---
    "poi_limit_mw": (1, 300),
    "curtailment_price": (0, 100),
    # --- Estrategia híbrida ---
    "pv_to_bess_share": (0.0, 1.0),
    # --- Modelos de ingreso (streams adicionales al arbitraje) ---
    "ppa_price": (20, 120),
    "ppa_energy_share": (0.0, 1.0),
    "capacity_price_eur_mw_year": (0, 60_000),
    "committed_mw": (0, 300),
    "secondary_band_up_mw": (0, 300),
    "secondary_band_down_mw": (0, 300),
    "secondary_price": (0, 150),
    "secondary_activation_rate": (0.0, 1.0),
}

DEFAULTS: dict[str, float] = {
    "capex_per_mw": 400_000,
    "opex_per_mw_year": 11_000,
    "discount_rate": 0.06,
    "avg_spread_price": 65,
    "tax_rate": 0.25,
    "inflation_rate": 0.02,
    "rated_power_mw": 50,
    "c_rate_inverse": 4,
    "nominal_power": 1.0,
    "eqo_cycles": 7_000,
    "lifespan_years": 15,
    "initial_soh": 1.0,
    "rte": 0.84,
    "degradation_per_cycle": 0.00003,
    "soh_min": 0.75,
    "max_dod": 0.95,
    "min_soc": 0.05,
    "year_cycles": 466.67,
    # --- Planta fotovoltaica (PV) hibridada ---
    "pv_peak_power_mwp": 60.0,        # DC (MWp)
    "pv_inverter_ac_mw": 48.0,        # AC nominal inversores → ILR ≈ 1.25
    "pv_performance_ratio": 0.80,     # PR global de planta
    "pv_annual_degradation": 0.005,   # 0.5%/año (típico c-Si)
    "pv_soiling_loss": 0.02,          # pérdidas por suciedad
    "pv_capex_per_mwp": 550_000,      # €/MWp utility-scale
    "pv_opex_per_mwp_year": 12_000,   # €/MWp/año
    "pv_latitude": 40.0,              # latitud (España peninsular)
    # --- Punto de interconexión (POI) / red ---
    "poi_limit_mw": 50.0,             # límite MW compartido PV+BESS
    "curtailment_price": 0.0,         # coste/penalización por curtailment €/MWh
    # --- Estrategia híbrida ---
    "pv_to_bess_share": 0.15,         # fracción de la generación PV desviada a cargar la BESS
    # --- Modelos de ingreso (streams adicionales al arbitraje) ---
    "ppa_price": 55.0,                # precio fijo PPA €/MWh
    "ppa_energy_share": 0.50,         # fracción de energía bajo PPA
    "capacity_price_eur_mw_year": 25_000,
    "committed_mw": 40.0,             # MW comprometidos en pago por capacidad
    "secondary_band_up_mw": 10.0,     # banda a subir reservada para secundaria
    "secondary_band_down_mw": 10.0,   # banda a bajar reservada para secundaria
    "secondary_price": 25.0,          # €/MW por banda reservada
    "secondary_activation_rate": 0.15,  # fracción media de activación de la banda
}

DASHBOARD_DEFAULTS: dict[str, float] = {
    "avg_spread_eur": 40.0,
    "future_cycles_per_day": 1.5,
    "future_rte": 0.84,
    "future_degradation_per_cycle": 0.00003,
    "future_max_dod": 0.90,
}

DASHBOARD_RANGES: dict[str, tuple[float, float]] = {
    "avg_spread_eur": (20, 80),
    "future_cycles_per_day": (0.5, 3.0),
    "future_rte": (0.80, 0.92),
    "future_degradation_per_cycle": (0.00005, 0.0002),
    "future_max_dod": (0.80, 0.95),
}
