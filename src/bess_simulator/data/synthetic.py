from __future__ import annotations

import numpy as np
import pandas as pd

from bess_simulator.config import INTERVAL_DURATION_H


# ---------------------------------------------------------------------------
# Referencias del modelo de datos sintéticos
# ---------------------------------------------------------------------------
# Precios OMIE:
#   - Datos horarios reales: https://www.omie.es/en/market-results/daily/daily-market/daily-hourly-price
#   - Spreads observados España: 25-67 €/MWh (Synertics, H1 2021-2023)
#   - Duck curve / ventanas arbitraje: exceso solar 11-15h, picos 08-10h y 19-21h
#
# Degradación LFP:
#   - Calendar aging <0.5%/año a bajo SOC/temp (MDPI Energies 2021, doi:10.3390/en14061732)
#   - Modelo usado: 1.5%/año (conservador, compatible con Ember ≤2%/año)
#   - Cycle aging: 0.01%/ciclo histórico (Ember: 10K-12K ciclos para 35% fade ≈ 0.003%/ciclo)
#   - Factores: SOC, temperatura, DOD, C-rate (MDPI Appl. Sci. 2025, doi:10.3390/app152312749)
#
# RTE:
#   - NREL ATB 2024: 85% referencia (https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage)
#   - Ember 2025: 90% AC-AC (https://ember-energy.org/latest-insights/how-cheap-is-battery-storage/)
#   - Modelo: inicia 87%, degrada 0.4%/año
#
# Temperatura:
#   - Modelo estacional peninsular (14-30°C) + operación (+1.5-3.5°C en descarga)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Precios OMIE — modelado experto mercado eléctrico español
# ---------------------------------------------------------------------------

def _omie_daily_shape(hours: np.ndarray, cfg: dict) -> np.ndarray:
    base = cfg["omie_base_price"]
    valley = cfg["omie_valley_amplitude"] * np.exp(-0.5 * ((hours - 4.0) / 1.5) ** 2)
    morning_peak = cfg["omie_morning_peak_amplitude"] * np.exp(-0.5 * ((hours - 9.0) / 1.2) ** 2)
    solar_dip = cfg["omie_solar_dip_amplitude"] * np.exp(-0.5 * ((hours - 13.5) / 1.5) ** 2)
    evening_peak = cfg["omie_evening_peak_amplitude"] * np.exp(-0.5 * ((hours - 20.0) / 1.2) ** 2)
    return base + valley + morning_peak + solar_dip + evening_peak


def _omie_weekly_factor(day_of_week: np.ndarray, cfg: dict) -> np.ndarray:
    factors = np.ones_like(day_of_week, dtype=float)
    factors[day_of_week == 5] = cfg["omie_saturday_factor"]
    factors[day_of_week == 6] = cfg["omie_sunday_factor"]
    return factors


def _omie_seasonal_factor(month: np.ndarray, cfg: dict) -> np.ndarray:
    table = np.array(cfg["omie_seasonal_factors"])
    return table[month - 1]


def _omie_price_profile(
    timestamps: pd.DatetimeIndex,
    rng: np.random.Generator,
    cfg: dict,
) -> np.ndarray:
    hours = timestamps.hour + timestamps.minute / 60.0
    day_of_week = timestamps.dayofweek
    month = timestamps.month

    shape = _omie_daily_shape(hours, cfg)
    weekly = _omie_weekly_factor(day_of_week, cfg)
    seasonal = _omie_seasonal_factor(month, cfg)

    n_days = int(np.ceil(len(timestamps) / 96)) + 1
    daily_noise = np.repeat(rng.normal(0, cfg["omie_daily_noise_std"], n_days), 96)[: len(timestamps)]
    intra_noise = rng.normal(0, cfg["omie_intraday_noise_std"], len(timestamps))

    prices = shape * weekly * seasonal + daily_noise + intra_noise
    return np.clip(prices, cfg["omie_price_floor"], cfg["omie_price_ceiling"])


# ---------------------------------------------------------------------------
# Ventanas de operación de arbitraje
# ---------------------------------------------------------------------------

def _is_charge_window(hours: np.ndarray, cfg: dict) -> np.ndarray:
    return (hours >= cfg["charge_start_hour"]) & (hours < cfg["charge_end_hour"])


def _is_discharge_window(hours: np.ndarray, cfg: dict) -> np.ndarray:
    morning = (hours >= cfg["discharge_am_start_hour"]) & (hours < cfg["discharge_am_end_hour"])
    evening = (hours >= cfg["discharge_pm_start_hour"]) & (hours < cfg["discharge_pm_end_hour"])
    return morning | evening


# ---------------------------------------------------------------------------
# Régimen pasado — datos expertos
# ---------------------------------------------------------------------------

def _generate_historical_regime(
    start_date: str,
    end_date: str,
    rated_power_mw: float,
    c_rate_inverse: float,
    seed: int | None,
    cfg: dict,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(start=start_date, end=end_date, freq="15min", inclusive="left")
    n = len(timestamps)
    if n == 0:
        return _empty_dashboard_df()

    hours = timestamps.hour + timestamps.minute / 60.0
    capacity_mwh = rated_power_mw * c_rate_inverse

    market_price = _omie_price_profile(timestamps, rng, cfg)
    is_charge = _is_charge_window(hours, cfg)
    is_discharge = _is_discharge_window(hours, cfg)

    utilization = rng.uniform(cfg["hist_utilization_min"], cfg["hist_utilization_max"], n)
    max_interval_energy = rated_power_mw * INTERVAL_DURATION_H
    energy_sold_mwh = np.where(
        is_discharge,
        max_interval_energy * utilization * 0.90,
        rng.uniform(0, max_interval_energy * 0.05, n),
    )

    capture_price = np.where(
        is_discharge,
        market_price * rng.uniform(0.92, 1.02, n),
        market_price * rng.uniform(0.70, 0.85, n),
    )
    capture_price = np.clip(capture_price, cfg["omie_price_floor"], cfg["omie_price_ceiling"])

    charge_cost_per_interval = np.where(is_charge, market_price, np.nan)
    df_tmp = pd.DataFrame({"ts": timestamps, "cc": charge_cost_per_interval})
    daily_charge_cost = df_tmp.set_index("ts").resample("D")["cc"].mean().ffill().bfill()
    charge_cost_expanded = daily_charge_cost.reindex(
        timestamps.floor("D")
    ).values

    spread = np.clip(capture_price - charge_cost_expanded, 0, None)
    income = energy_sold_mwh * spread

    daily_fec = rng.uniform(0.8, 1.8, int(np.ceil(n / 96)) + 1)
    interval_fec = np.repeat(daily_fec / 96, 96)[: n]

    cumulative_days = (timestamps - timestamps[0]).total_seconds().values / 86400.0
    calendar_loss = cfg["calendar_aging_rate"] * (cumulative_days / 365.0)
    cumulative_cycles = np.cumsum(interval_fec)
    cycle_loss = cumulative_cycles * cfg["historical_cycle_degradation"]
    soh = np.clip(1.0 - calendar_loss - cycle_loss + rng.normal(0, 0.0008, n), 0.80, 1.0)

    rte_base = cfg["rte_base_historical"] - cfg["rte_annual_decay"] * (cumulative_days / 365.0)
    rte = np.clip(rte_base + rng.normal(0, 0.005, n), cfg["rte_floor"], cfg["rte_ceiling"])

    # --- Temperatura: estacional + diaria ---
    day_of_year = timestamps.dayofyear
    temp_seasonal = 22.0 + 8.0 * np.sin((day_of_year - 80) * 2 * np.pi / 365)
    temp_daily = 3.0 * np.sin((hours - 14) * np.pi / 12)
    temp_operation = np.where(is_discharge, rng.uniform(1.5, 3.5, n), 0)
    temperature = np.clip(
        temp_seasonal + temp_daily + temp_operation + rng.normal(0, 1.2, n),
        5.0, 45.0,
    )

    # Inyección de anomalías controladas (eventos históricos críticos).
    temperature, rte = _inject_anomalies(temperature, rte, timestamps, rng, cfg)

    return pd.DataFrame({
        "timestamp": timestamps,
        "income": income,
        "capture_price": capture_price,
        "average_market_price": market_price,
        "energy_sold_mwh": energy_sold_mwh,
        "soh": soh,
        "cycles": interval_fec,
        "temperature": temperature,
        "rte": rte,
        "is_forecast": False,
    })


# ---------------------------------------------------------------------------
# Inyección de anomalías controladas (eventos históricos APM)
# ---------------------------------------------------------------------------

def _inject_anomalies(
    temperature: np.ndarray,
    rte: np.ndarray,
    timestamps: pd.DatetimeIndex,
    rng: np.random.Generator,
    cfg: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Inyecta episodios puntuales fuera de rango en el histórico.

    Simula anomalías reales del activo que deben quedar registradas como
    eventos críticos (seguridad/garantía):

      - Sobre-temperatura: picos térmicos por encima del umbral de seguridad.
      - Caída de RTE: pérdidas de rendimiento por debajo del mínimo contractual.

    Los episodios duran 1-4 intervalos consecutivos y se aplican DESPUÉS del
    recorte base, de modo que persistan. Es determinista para una semilla dada.
    """
    if not cfg.get("anomaly_enable", False):
        return temperature, rte

    n = len(temperature)
    if n == 0:
        return temperature, rte

    years = max((timestamps[-1] - timestamps[0]).total_seconds() / (365.0 * 86400.0), 1e-9)
    temperature = np.asarray(temperature, dtype=float).copy()
    rte = np.asarray(rte, dtype=float).copy()

    def _apply_events(arr, events_per_year, value, lo, hi, jitter):
        n_events = int(round(events_per_year * years))
        if n_events <= 0:
            return arr
        starts = rng.integers(0, n, size=n_events)
        for s in starts:
            span = int(rng.integers(1, 5))  # 1-4 intervalos
            end = min(s + span, n)
            noisy = value + rng.normal(0.0, jitter, end - s)
            arr[s:end] = np.clip(noisy, lo, hi)
        return arr

    # Sobre-temperatura (seguridad).
    temperature = _apply_events(
        temperature,
        cfg.get("anomaly_temp_events_per_year", 0.0),
        cfg.get("anomaly_temp_peak_c", 46.0),
        lo=cfg.get("alarm_temp_critical_c", 40.0) + 0.5,
        hi=60.0,
        jitter=1.5,
    )

    # Caída de RTE (garantía de rendimiento).
    rte = _apply_events(
        rte,
        cfg.get("anomaly_rte_events_per_year", 0.0),
        cfg.get("anomaly_rte_dip", 0.72),
        lo=0.50,
        hi=cfg.get("alarm_rte_min", 0.78) - 0.005,
        jitter=0.01,
    )

    return temperature, rte


# ---------------------------------------------------------------------------
# Régimen futuro — proyección paramétrica
# ---------------------------------------------------------------------------

def _generate_future_regime(
    start_date: str,
    end_date: str,
    rated_power_mw: float,
    c_rate_inverse: float,
    initial_soh: float,
    initial_cumulative_cycles: float,
    avg_spread_eur: float,
    cycles_per_day: float,
    rte: float,
    degradation_per_cycle: float,
    max_dod: float,
    seed: int | None,
    cfg: dict,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed if seed is None else seed + 1000)
    timestamps = pd.date_range(start=start_date, end=end_date, freq="15min", inclusive="left")
    n = len(timestamps)
    if n == 0:
        return _empty_dashboard_df()

    hours = timestamps.hour + timestamps.minute / 60.0

    base_prices = _omie_price_profile(timestamps, rng, cfg)
    spread_scale = avg_spread_eur / cfg["omie_base_price"]
    market_price = base_prices * spread_scale
    market_price = np.clip(market_price, cfg["omie_price_floor"], 200.0)

    is_discharge = _is_discharge_window(hours, cfg)
    is_charge = _is_charge_window(hours, cfg)

    max_interval_energy = rated_power_mw * INTERVAL_DURATION_H
    utilization = rng.uniform(cfg["future_utilization_min"], cfg["future_utilization_max"], n)
    energy_sold_mwh = np.where(
        is_discharge,
        max_interval_energy * max_dod * utilization,
        rng.uniform(0, max_interval_energy * 0.03, n),
    )

    capture_price = np.where(
        is_discharge,
        market_price * rng.uniform(0.93, 1.01, n),
        market_price * rng.uniform(0.72, 0.85, n),
    )
    capture_price = np.clip(capture_price, cfg["omie_price_floor"], 200.0)

    charge_cost_per_interval = np.where(is_charge, market_price, np.nan)
    df_tmp = pd.DataFrame({"ts": timestamps, "cc": charge_cost_per_interval})
    daily_charge_cost = df_tmp.set_index("ts").resample("D")["cc"].mean().ffill().bfill()
    charge_cost_expanded = daily_charge_cost.reindex(
        timestamps.floor("D")
    ).values

    spread = np.clip(capture_price - charge_cost_expanded, 0, None)
    income = energy_sold_mwh * spread

    interval_fec = np.full(n, cycles_per_day / 96)
    interval_fec += rng.normal(0, interval_fec * 0.05, n)
    interval_fec = np.clip(interval_fec, 0, None)

    cumulative_days = (timestamps - timestamps[0]).total_seconds().values / 86400.0
    calendar_loss = cfg["calendar_aging_rate"] * (cumulative_days / 365.0)
    cumulative_new_cycles = np.cumsum(interval_fec)
    cycle_loss = cumulative_new_cycles * degradation_per_cycle
    soh = np.clip(initial_soh - calendar_loss - cycle_loss, 0.50, 1.0)

    rte_arr = np.clip(rte + rng.normal(0, 0.008, n), cfg["rte_floor"], cfg["rte_ceiling"])

    # --- Temperatura ---
    day_of_year = timestamps.dayofyear
    temp_seasonal = 22.0 + 8.0 * np.sin((day_of_year - 80) * 2 * np.pi / 365)
    temp_daily = 3.0 * np.sin((hours - 14) * np.pi / 12)
    temperature = np.clip(
        temp_seasonal + temp_daily + rng.normal(0, 1.0, n),
        5.0, 45.0,
    )

    return pd.DataFrame({
        "timestamp": timestamps,
        "income": income,
        "capture_price": capture_price,
        "average_market_price": market_price,
        "energy_sold_mwh": energy_sold_mwh,
        "soh": soh,
        "cycles": interval_fec,
        "temperature": temperature,
        "rte": rte_arr,
        "is_forecast": True,
    })


# ---------------------------------------------------------------------------
# Calibración a los agregados del Simulador ROI
# ---------------------------------------------------------------------------
# El Simulador ROI es el motor de referencia del escenario del operador. Su
# proyección es analítica y "plana". El dashboard reproduce esa misma realidad
# pero con variabilidad intradía estocástica (perfil OMIE + ventanas de
# arbitraje). Para que ambas pantallas sean COHERENTES, calibramos cada tramo
# del dashboard a los agregados anuales del simulador, CONSERVANDO la forma
# estocástica intradía:
#   - histórico  → año 1 del simulador (income y SoH final)
#   - proyección → año 2 del simulador (income y SoH final)
# El escalado es uniforme (income y energía a la vez), de modo que el precio
# realista no se altera y el detalle intradía se mantiene.

def _calibrate_segment(
    df: pd.DataFrame,
    target_income: float | None = None,
    soh_start: float | None = None,
    target_soh_end: float | None = None,
) -> pd.DataFrame:
    """Escala un tramo (histórico o proyección) a los agregados del simulador.

    - ``target_income``: income total objetivo del tramo (€). Escala income y
      energía vendida por el mismo factor (preserva el precio implícito y el
      perfil intradía).
    - ``soh_start`` / ``target_soh_end``: ancla la trayectoria de SoH para que
      arranque en ``soh_start`` y termine en ``target_soh_end``, conservando la
      forma (degradación reescalada proporcionalmente).
    """
    if df.empty:
        return df
    df = df.copy()

    if target_income is not None:
        current = float(df["income"].sum())
        if current > 0:
            scale = target_income / current
            df["income"] = df["income"] * scale
            df["energy_sold_mwh"] = df["energy_sold_mwh"] * scale

    if target_soh_end is not None:
        soh = df["soh"].to_numpy(dtype=float)
        start = float(soh_start) if soh_start is not None else float(soh[0])
        deg = start - soh  # degradación acumulada relativa al inicio del tramo
        final_deg = float(deg[-1])
        target_deg = start - float(target_soh_end)
        if final_deg > 1e-9 and target_deg > 0:
            deg_scaled = deg * (target_deg / final_deg)
            df["soh"] = np.clip(start - deg_scaled, 0.50, 1.0)
        else:
            # Sin degradación apreciable en la forma base: rampa lineal al objetivo.
            ramp = np.linspace(0.0, max(target_deg, 0.0), len(soh))
            df["soh"] = np.clip(start - ramp, 0.50, 1.0)

    return df


def _calibrate_future_multiyear(
    df: pd.DataFrame,
    hoy: str,
    yearly_income: tuple,
    yearly_soh_end: tuple,
    soh_start: float,
) -> pd.DataFrame:
    """Calibra la proyección año a año a los agregados del Simulador ROI.

    La proyección abarca toda la vida útil restante. Cada bloque anual i (los
    365 días i-ésimos desde HOY) se ajusta al año (i+2) del Simulador
    (``yearly_*[i+1]``), porque el año 1 ya es el histórico. Income y energía se
    escalan juntos (preserva el precio y el detalle intradía); la trayectoria de
    SoH se ancla en los extremos anuales con continuidad entre años.
    """
    if df.empty or not yearly_income:
        return df
    df = df.copy()

    ts = pd.to_datetime(df["timestamp"])
    hoy_ts = pd.Timestamp(str(hoy))
    year_idx = np.floor(
        (ts - hoy_ts).dt.total_seconds().to_numpy() / (365.0 * 86400.0)
    ).astype(int)

    income = np.array(df["income"], dtype=float)
    energy = np.array(df["energy_sold_mwh"], dtype=float)
    base_soh = np.array(df["soh"], dtype=float)
    new_soh = base_soh.copy()

    n_years = len(yearly_income)
    prev_soh = float(soh_start)
    for k in range(int(year_idx.max()) + 1):
        mask = year_idx == k
        n_block = int(mask.sum())
        if n_block == 0:
            continue
        sim_i = min(k + 1, n_years - 1)  # año (k+2) del simulador; 0=histórico
        # Fracción de año cubierta por el bloque (1.0 para años completos; <1 en
        # un bloque final parcial). Evita inflar income/degradación en sobrantes.
        frac = min(n_block / (365.0 * 96), 1.0)

        # Income / energía → objetivo anual del simulador (proporcional al bloque).
        target_inc = float(yearly_income[sim_i]) * frac
        cur = float(income[mask].sum())
        if cur > 0:
            scale = target_inc / cur
            income[mask] = income[mask] * scale
            energy[mask] = energy[mask] * scale

        # SoH → ancla extremos del bloque conservando la forma de degradación.
        target_deg = (prev_soh - float(yearly_soh_end[sim_i])) * frac
        seg = base_soh[mask]
        seg_start = float(seg[0])
        deg = seg_start - seg
        final_deg = float(deg[-1])
        if final_deg > 1e-9 and target_deg > 0:
            new_soh[mask] = prev_soh - deg * (target_deg / final_deg)
        else:
            new_soh[mask] = prev_soh - np.linspace(0.0, max(target_deg, 0.0), n_block)
        prev_soh = prev_soh - target_deg

    df["income"] = income
    df["energy_sold_mwh"] = energy
    df["soh"] = np.clip(new_soh, 0.50, 1.0)
    return df


# ---------------------------------------------------------------------------
# Función principal pública
# ---------------------------------------------------------------------------

def generate_dashboard_dataset(
    start_date: str = "2024-06-01",
    hoy: str = "2025-06-01",
    end_date: str = "2026-06-01",
    rated_power_mw: float = 50,
    c_rate_inverse: float = 4,
    avg_spread_eur: float = 40.0,
    future_cycles_per_day: float = 1.5,
    future_rte: float = 0.84,
    future_degradation_per_cycle: float = 0.0001,
    max_dod: float = 0.90,
    seed: int | None = 42,
    advanced_config: dict | None = None,
    calibration: dict | None = None,
) -> pd.DataFrame:
    """Genera el dataset del dashboard (histórico + proyección).

    Si se pasa ``calibration`` (agregados del Simulador ROI), cada tramo se
    ajusta a esos valores objetivo conservando la variabilidad estocástica:
      ``{"yearly_income": (...), "yearly_soh_end": (...)}`` (índice 0 = año 1).
    """
    from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG
    cfg = advanced_config or DEFAULT_ADVANCED_CONFIG
    calibration = calibration or {}
    yearly_income = calibration.get("yearly_income")
    yearly_soh_end = calibration.get("yearly_soh_end")

    hist = _generate_historical_regime(
        start_date=start_date,
        end_date=hoy,
        rated_power_mw=rated_power_mw,
        c_rate_inverse=c_rate_inverse,
        seed=seed,
        cfg=cfg,
    )

    # Calibración del histórico al año 1 del simulador.
    if yearly_income:
        hist = _calibrate_segment(
            hist,
            target_income=float(yearly_income[0]),
            soh_start=1.0,
            target_soh_end=float(yearly_soh_end[0]),
        )

    if hist.empty:
        initial_soh = 1.0
        initial_cumulative_cycles = 0.0
    else:
        initial_soh = float(hist["soh"].iloc[-1])
        initial_cumulative_cycles = float(hist["cycles"].sum())

    future = _generate_future_regime(
        start_date=hoy,
        end_date=end_date,
        rated_power_mw=rated_power_mw,
        c_rate_inverse=c_rate_inverse,
        initial_soh=initial_soh,
        initial_cumulative_cycles=initial_cumulative_cycles,
        avg_spread_eur=avg_spread_eur,
        cycles_per_day=future_cycles_per_day,
        rte=future_rte,
        degradation_per_cycle=future_degradation_per_cycle,
        max_dod=max_dod,
        seed=seed,
        cfg=cfg,
    )

    # Calibración año a año de la proyección a los años 2..N del simulador. La
    # trayectoria de SoH arranca donde termina el histórico ya calibrado.
    if yearly_income:
        future = _calibrate_future_multiyear(
            future,
            hoy=hoy,
            yearly_income=yearly_income,
            yearly_soh_end=yearly_soh_end,
            soh_start=initial_soh,
        )

    return pd.concat([hist, future], ignore_index=True)


# ---------------------------------------------------------------------------
# Agregación diaria (compatible con ambos regímenes)
# ---------------------------------------------------------------------------

def aggregate_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    agg_dict = {
        "income": "sum",
        "capture_price": "mean",
        "average_market_price": "mean",
        "energy_sold_mwh": "sum",
        "soh": "last",
        "cycles": "sum",
        "temperature": "mean",
        "rte": "mean",
        "is_forecast": "first",
    }
    daily = df.set_index("timestamp").resample("D").agg(agg_dict).reset_index()
    return daily


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_dashboard_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "timestamp", "income", "capture_price", "average_market_price",
        "energy_sold_mwh", "soh", "cycles", "temperature", "rte", "is_forecast",
    ])
