from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DEFAULT_ADVANCED_CONFIG: dict = {
    # --- Modelo de Degradación y Eficiencia ---
    "calendar_aging_rate": 0.015,
    "historical_cycle_degradation": 0.00003,
    "rte_annual_decay": 0.001,
    "rte_base_historical": 0.87,
    "rte_floor": 0.75,
    "rte_ceiling": 0.95,
    # --- Modelo de Precios OMIE ---
    "omie_base_price": 55.0,
    "omie_valley_amplitude": -10.0,
    "omie_morning_peak_amplitude": 30.0,
    "omie_solar_dip_amplitude": -15.0,
    "omie_evening_peak_amplitude": 38.0,
    "omie_saturday_factor": 0.82,
    "omie_sunday_factor": 0.78,
    "omie_seasonal_factors": [1.12, 1.10, 0.95, 0.85, 0.85, 0.95, 1.10, 1.10, 1.00, 0.95, 1.05, 1.15],
    "omie_daily_noise_std": 5.0,
    "omie_intraday_noise_std": 2.0,
    "omie_price_floor": 20.0,
    "omie_price_ceiling": 150.0,
    # --- Ventanas de Arbitraje ---
    "charge_start_hour": 2,
    "charge_end_hour": 6,
    "discharge_am_start_hour": 8,
    "discharge_am_end_hour": 10,
    "discharge_pm_start_hour": 19,
    "discharge_pm_end_hour": 21,
    # --- Sinergia Híbrida PV→BESS (reconciliación anual) ---
    # Precio de carga de red EVITADO (€/MWh) al cargar la BESS con PV en lugar de
    # comprar en pool en horas valle. La energía PV→BESS se asigna a coste CERO,
    # por lo que este valor es el ahorro neto (crédito de sinergia) por MWh solar
    # cargado. Proxy del precio OMIE en ventana de carga (valle).
    "bess_grid_charge_price": 35.0,
    # Curtailment estimado por concurrencia en el POI compartido (fracción de la
    # energía PV inyectada a red que se pierde por solapamiento PV+BESS y órdenes
    # de red). Un despacho inteligente evita la mayor parte; se modela el residual.
    "poi_concurrency_curtail_pct": 0.03,
    # --- Operación Histórica ---
    "hist_utilization_min": 0.70,
    "hist_utilization_max": 0.92,
    "future_utilization_min": 0.75,
    "future_utilization_max": 0.90,
    # --- Variabilidad Estocástica (Simulador) ---
    "sim_cycle_variation": 0.40,
    "sim_rte_noise_std": 0.003,
    "sim_price_floor_factor": 0.70,
    "sim_price_range_factor": 1.00,
    # --- Modelo Meteorológico (generación PV) ---
    "meteo_kt_mean": 0.70,          # clearness index medio (0=cubierto, 1=despejado)
    "meteo_kt_ar": 0.92,            # persistencia de la nubosidad (autocorrelación)
    "meteo_kt_noise_std": 0.12,     # variabilidad estocástica de la nubosidad
    "meteo_kt_min": 0.10,
    "meteo_kt_max": 1.00,
    "meteo_temp_mean": 15.0,        # temperatura ambiente media anual (°C)
    "meteo_temp_seasonal_amp": 9.0, # amplitud estacional (°C)
    "meteo_temp_daily_amp": 6.0,    # amplitud diaria (°C)
    "meteo_temp_noise_std": 1.2,
    "meteo_wind_mean": 3.0,         # velocidad de viento media (m/s)
    "meteo_wind_std": 1.0,
    "meteo_humidity_mean": 0.55,    # humedad relativa media (0..1)
    "meteo_humidity_cloud_coupling": 0.30,  # +humedad con nubosidad
    # --- Modelo Fotovoltaico (generación PV) ---
    "pv_temp_coeff_pmax": -0.0035,  # coef. temperatura de potencia (1/°C), c-Si
    "pv_noct": 45.0,                # Nominal Operating Cell Temperature (°C)
    "pv_inverter_efficiency": 0.985,  # eficiencia de conversión DC→AC
    "pv_dc_losses": 0.02,           # pérdidas DC adicionales (cableado, mismatch)
    # --- Umbrales de Recomendación ---
    "rec_roi_high_threshold": 0.08,
    "rec_roi_diversify_band": 0.02,
    "rec_discount_rate_ok": 0.08,
    "rec_discount_rate_warning": 0.10,
    "rec_opex_ok": 10_000,
    "rec_opex_warning": 15_000,
    "rec_rte_ok": 0.86,
    "rec_rte_warning": 0.80,
    "rec_lifespan_ok": 15,
    "rec_lifespan_warning": 10,
    "rec_price_ok": 45.0,
    "rec_price_warning": 30.0,
    # --- Umbrales de Alerta Histórica (registro de eventos críticos APM) ---
    "alarm_temp_critical_c": 40.0,   # temperatura crítica de seguridad (°C)
    "alarm_rte_min": 0.78,           # RTE mínimo contractual (garantía)
    "alarm_soh_min": 0.80,           # SoH mínimo garantizado (salud)
    # --- Umbrales de Garantía (warranty compliance, vista de elementos) ---
    "warranty_soh_spread_max_pp": 5.0,   # dispersión máx. de SoH del grupo (pp)
    "warranty_cycles_max": 6000.0,       # tope contractual de ciclos equivalentes
    "warranty_dod_max_pct": 100.0,       # DoD máx. admisible por ciclo (%)
    # --- Inyección de Anomalías Sintéticas (solo histórico) ---
    "anomaly_enable": True,          # activa la inyección de eventos fuera de rango
    "anomaly_temp_events_per_year": 6.0,   # episodios de sobre-temperatura/año
    "anomaly_temp_peak_c": 46.0,     # pico de temperatura del episodio (°C)
    "anomaly_rte_events_per_year": 4.0,    # episodios de caída de RTE/año
    "anomaly_rte_dip": 0.72,         # RTE alcanzado en la caída
}


def load_config(db_path: Path) -> dict:
    config = dict(DEFAULT_ADVANCED_CONFIG)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT key, value FROM app_config").fetchall()
        for key, value in rows:
            if key in config:
                config[key] = json.loads(value)
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return config


def save_config(db_path: Path, config: dict) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        for key, value in config.items():
            conn.execute(
                "INSERT OR REPLACE INTO app_config (key, value, updated_at) "
                "VALUES (?, ?, datetime('now'))",
                (key, json.dumps(value)),
            )
        conn.commit()
    finally:
        conn.close()


def reset_config(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM app_config")
        conn.commit()
    finally:
        conn.close()
