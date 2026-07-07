"""Agregación de planta híbrida para la pantalla general (Fase 6).

Calcula, a partir del "dataset activo" (histórico + proyección sintéticos) y
del dimensionado del operador:

  - :func:`compute_plant_summary`: especificaciones, energía entregada en el
    periodo y KPIs operativos (disponibilidad, rango de SoC, RTE, ciclos, SoH,
    potencia media), además del recuento de subelementos para el acceso a la
    monitorización.
  - :func:`compute_kpi_deviations`: desvío porcentual de cada KPI frente a su
    valor de negocio deseable (para anotar la tarjeta con un superíndice).
  - :func:`build_power_soc_series`: serie temporal continua (potencia PV +
    carga/descarga BESS + SoC) sobre el rango seleccionado, encadenando varias
    estrategias de despacho día a día.
  - :func:`slice_bundle`: recorta el dataset activo a un rango de visualización
    para que todas las vistas reaccionen a la misma fuente de datos.

Es lógica de visualización del prototipo: usa heurísticas de despacho simples
para construir los perfiles representativos, no un optimizador de despacho.
Todo deriva del mismo ``bundle`` (dataset activo) para garantizar coherencia
entre las distintas vistas.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from bess_simulator.config import INTERVAL_DURATION_H
from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import PlantSummary

# Resolución base de la serie potencia-SoC y nº máximo de puntos a dibujar
# (la resolución se degrada automáticamente en rangos largos para no saturar).
_PROFILE_STEP_MIN = 5
_MAX_SERIES_POINTS = 2600

# Plan de servicios de una quincena (15 días) que se repite a lo largo del rango.
# Cada día tiene un servicio dominante; la combinación da variedad realista
# manteniendo una unidad que se repite de forma consistente.
_FORTNIGHT_PLAN = [
    "Arbitraje",
    "Arbitraje + secundaria",
    "Energy shifting",
    "Arbitraje",
    "Arbitraje + secundaria",
    "Energy shifting",
    "Arbitraje + secundaria",
    "Arbitraje",
    "Energy shifting",
    "Arbitraje + secundaria",
    "Arbitraje",
    "Energy shifting",
    "Arbitraje + secundaria",
    "Energy shifting",
    "Arbitraje",
]

# --- Caso de uso multiservicio GARANTIZADO (figura de referencia) ---
# Ventana de 5 días con un perfil intradía claro de 5 fases que se fuerza
# siempre para estas fechas del dataset, de modo que el comportamiento del
# caso de uso quede asegurado y sea reproducible para demostración:
#   00–06h  Carga de red (precio bajo, valle nocturno)
#   06–14h  FV + carga de excedentes (autoconsumo, reserva backup)
#   14–20h  Modulación/carga suave sin exportación positiva
#   18–22h  aFRR absorbente sin conflicto con el POI
#   20–24h  Descarga nocturna principal (sin PV)
_SHOWCASE_LABEL = "Caso de uso multiservicio"
SHOWCASE_START = pd.Timestamp("2025-06-01")
SHOWCASE_END = pd.Timestamp("2025-06-05")  # inclusive (5 días: 1–5 jun 2025)

# Valores de negocio deseables para anotar el desvío de cada KPI.
_KPI_TARGETS = {
    "availability": 98.0,   # % de disponibilidad objetivo
    "soc_usable": 90.0,     # puntos de ventana útil de SoC objetivo
    "rte": 0.88,            # round-trip efficiency objetivo
    "soh": 0.90,            # suelo de SoH deseable
}

# Valores de negocio deseables para los KPIs fotovoltaicos.
# Referencias: planta FV fija en latitud media (España).
_PV_KPI_TARGETS = {
    "pv_capacity_factor": 0.22,   # CF objetivo sobre potencia AC del inversor
    "pv_performance_ratio": 0.80, # PR objetivo de una planta bien mantenida
    "pv_availability": 99.0,       # % de horas de sol con producción objetivo
}

# Constante de irradiancia en condiciones estándar (STC) para el PR.
_STC_IRRADIANCE_KW_M2 = 1.0  # kW/m²


def slice_bundle(bundle: dict, start, end) -> dict:
    """Recorta ``df`` y ``pv`` del bundle al rango ``[start, end]``.

    Devuelve un nuevo dict (no muta el original) con las capas filtradas y los
    metadatos de rango actualizados. El resto de capas se conservan tal cual.
    """
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)  # incluye el día final

    out = dict(bundle)
    for key in ("df", "pv", "meteo"):
        frame = bundle.get(key)
        if frame is not None and not frame.empty and "timestamp" in frame:
            mask = (frame["timestamp"] >= start_ts) & (frame["timestamp"] < end_ts)
            out[key] = frame.loc[mask].reset_index(drop=True)
    out["start"] = start
    out["end"] = end
    return out


def compute_plant_summary(bundle: dict, inputs: SimulationInputs) -> PlantSummary:
    """Agrega el dataset activo en un :class:`PlantSummary`."""
    df = bundle.get("df")
    pv = bundle.get("pv")
    params = bundle.get("params", {})

    summary = PlantSummary(
        location=str(params.get("location", "Castilla-La Mancha, España")),
        nominal_power_mw=float(inputs.output_power_mw),
        bess_capacity_mwh=float(inputs.total_capacity_mwh),
        pv_peak_mwp=float(inputs.pv.peak_power_mwp),
        pv_inverter_mw=float(inputs.pv.inverter_ac_mw),
        ilr=float(inputs.pv.dc_ac_ratio),
        poi_limit_mw=float(inputs.grid.poi_limit_mw),
    )

    if df is None or df.empty:
        return summary

    # --- Energía entregada en el periodo ---
    discharge_mwh = float(df["energy_sold_mwh"].sum())
    mean_rte = float(df["rte"].mean()) if "rte" in df else inputs.efficiency.rte
    charge_mwh = discharge_mwh / mean_rte if mean_rte > 0 else 0.0

    pv_ac_mwh = 0.0
    if pv is not None and not pv.empty and "p_ac_mw" in pv:
        pv_ac_mwh = float(pv["p_ac_mw"].sum() * INTERVAL_DURATION_H)

    exported_mwh = discharge_mwh + pv_ac_mwh   # descarga BESS + generación PV a red
    imported_mwh = charge_mwh                  # carga de la BESS
    total_throughput = exported_mwh + imported_mwh

    summary.exported_gwh = exported_mwh / 1000.0
    summary.imported_gwh = imported_mwh / 1000.0
    summary.pv_generated_gwh = pv_ac_mwh / 1000.0
    summary.net_mwh = exported_mwh - imported_mwh
    if total_throughput > 0:
        summary.exported_pct = 100.0 * exported_mwh / total_throughput
        summary.imported_pct = 100.0 * imported_mwh / total_throughput

    # --- KPIs operativos ---
    # Disponibilidad: fracción de intervalos con SoH por encima del mínimo
    # garantizado (proxy de activo "disponible").
    if "soh" in df:
        summary.time_based_availability = 100.0 * float(
            (df["soh"] >= inputs.efficiency.soh_min).mean()
        )
        summary.state_of_health = float(df["soh"].iloc[-1])

    # Ventana operativa de SoC: limitada por el DoD máximo.
    summary.soc_min_pct = 100.0 * (1.0 - inputs.efficiency.max_dod)
    summary.soc_max_pct = 100.0

    summary.roundtrip_efficiency = mean_rte
    summary.cycle_count = float(df["cycles"].sum()) if "cycles" in df else 0.0

    period_hours = len(df) * INTERVAL_DURATION_H
    if period_hours > 0:
        summary.charge_discharge_avg_power_mw = discharge_mwh / period_hours

    # --- KPIs fotovoltaicos (fórmulas estándar de negocio, IEC 61724) ---
    _compute_pv_kpis(summary, bundle, inputs, pv_ac_mwh)

    # --- Recuento de subelementos (escala con el dimensionado) ---
    rated_power = max(inputs.bess.rated_power_mw, 1.0)
    summary.meters = 1
    summary.pcs = max(1, round(rated_power / 2.5))
    summary.bess_modules = max(1, round(inputs.total_capacity_mwh / 2.5))
    summary.power_stations = max(1, round(rated_power / 12.0))

    return summary


def compute_kpi_deviations(
    summary: PlantSummary, inputs: SimulationInputs, n_days: int
) -> dict[str, float]:
    """Desvío porcentual de cada KPI frente a su valor de negocio deseable.

    Positivo = por encima del objetivo (favorable); negativo = por debajo.
    Para ``cycles`` y ``avg_power`` el objetivo es dinámico (depende del periodo
    de visualización y del dimensionado).
    """
    def _dev(actual: float, expected: float) -> float:
        if expected == 0:
            return 0.0
        return (actual - expected) / expected * 100.0

    usable = summary.soc_max_pct - summary.soc_min_pct
    days = max(int(n_days), 1)
    expected_cycles = inputs.daily_cycles * days
    expected_avg_power = inputs.daily_cycles * inputs.total_capacity_mwh / 24.0

    return {
        "availability": _dev(summary.time_based_availability, _KPI_TARGETS["availability"]),
        "soc_range": _dev(usable, _KPI_TARGETS["soc_usable"]),
        "rte": _dev(summary.roundtrip_efficiency, _KPI_TARGETS["rte"]),
        "cycles": _dev(summary.cycle_count, expected_cycles),
        "soh": _dev(summary.state_of_health, _KPI_TARGETS["soh"]),
        "avg_power": _dev(summary.charge_discharge_avg_power_mw, expected_avg_power),
    }


def _compute_pv_kpis(
    summary: PlantSummary, bundle: dict, inputs: SimulationInputs, pv_ac_mwh: float
) -> None:
    """Calcula los KPIs fotovoltaicos del periodo y los escribe en ``summary``.

    Fórmulas estándar de negocio (IEC 61724) a partir del dataset sintético:

      - Producción AC:        E_AC = Σ P_ac · Δt                         [MWh]
      - Irradiación POA:      H_POA = Σ POA · Δt                         [Wh/m²]
      - Capacity Factor:      CF = E_AC / (P_ac_inversor · T)           (base AC)
      - Performance Ratio:    PR = (E_AC / P_dc_pico) / (H_POA / G_STC)
      - Disponibilidad:       % de intervalos con sol (GHI cielo claro > 0)
                              en los que la planta produce (P_ac > 0).
    """
    pv = bundle.get("pv")
    meteo = bundle.get("meteo")
    if pv is None or pv.empty or "p_ac_mw" not in pv:
        return

    # Producción AC entregada en el periodo.
    summary.pv_production_mwh = pv_ac_mwh

    # Irradiación POA acumulada (Wh/m² = W/m² · h).
    if "poa" in pv:
        summary.pv_irradiation_wh_m2 = float(pv["poa"].sum() * INTERVAL_DURATION_H)

    # Capacity Factor sobre la potencia AC nominal del inversor.
    pv_hours = len(pv) * INTERVAL_DURATION_H
    summary.pv_period_hours = pv_hours
    cf_denom = inputs.pv.inverter_ac_mw * pv_hours
    if cf_denom > 0:
        summary.pv_capacity_factor = pv_ac_mwh / cf_denom

    # Performance Ratio (IEC 61724): rendimiento final / rendimiento de referencia.
    h_poa_kwh = summary.pv_irradiation_wh_m2 / 1000.0  # kWh/m²
    if inputs.pv.peak_power_mwp > 0 and h_poa_kwh > 0:
        final_yield = pv_ac_mwh / inputs.pv.peak_power_mwp          # h
        reference_yield = h_poa_kwh / _STC_IRRADIANCE_KW_M2         # h
        if reference_yield > 0:
            summary.pv_performance_ratio = final_yield / reference_yield

    # Irradiación de cielo claro del periodo (referencia para el desvío).
    if meteo is not None and not meteo.empty and "ghi_clearsky" in meteo:
        summary.pv_clearsky_wh_m2 = float(
            meteo["ghi_clearsky"].sum() * INTERVAL_DURATION_H
        )

    # Disponibilidad técnica en horas de sol.
    if meteo is not None and not meteo.empty and "ghi_clearsky" in meteo:
        daylight = meteo["ghi_clearsky"].to_numpy() > 0.0
        producing = pv["p_ac_mw"].to_numpy() > 0.0
        n = min(len(daylight), len(producing))
        daylight, producing = daylight[:n], producing[:n]
        n_daylight = int(daylight.sum())
        if n_daylight > 0:
            summary.pv_availability = (
                100.0 * float((producing & daylight).sum()) / n_daylight
            )


def compute_pv_kpi_deviations(
    summary: PlantSummary, inputs: SimulationInputs
) -> dict[str, float]:
    """Desvío porcentual de los KPIs fotovoltaicos frente a su valor deseable.

    Para ``irradiation`` y ``production`` el objetivo es dinámico:

      - ``irradiation``: desvío frente a la irradiación de cielo claro del
        periodo (negativo = pérdidas por nubosidad).
      - ``production``: desvío frente a la energía esperada con el Capacity
        Factor objetivo (E_esp = CF_obj · P_ac_inversor · T).
    """
    def _dev(actual: float, expected: float) -> float:
        if expected == 0:
            return 0.0
        return (actual - expected) / expected * 100.0

    # Referencia de irradiación: potencial de cielo claro del periodo.
    clearsky_wh_m2 = summary.pv_clearsky_wh_m2
    irr_dev = _dev(summary.pv_irradiation_wh_m2, clearsky_wh_m2) if clearsky_wh_m2 else 0.0

    # Referencia de producción: energía esperada con el CF objetivo.
    pv_hours = summary.pv_period_hours
    expected_production = (
        _PV_KPI_TARGETS["pv_capacity_factor"] * inputs.pv.inverter_ac_mw * pv_hours
    )

    return {
        "pv_capacity_factor": _dev(
            summary.pv_capacity_factor, _PV_KPI_TARGETS["pv_capacity_factor"]
        ),
        "pv_performance_ratio": _dev(
            summary.pv_performance_ratio, _PV_KPI_TARGETS["pv_performance_ratio"]
        ),
        "pv_availability": _dev(
            summary.pv_availability, _PV_KPI_TARGETS["pv_availability"]
        ),
        "pv_irradiation": irr_dev,
        "pv_production": _dev(summary.pv_production_mwh, expected_production),
    }


def _day_power_shape(service: str, h: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Forma de despacho intradía sin escalar (negativo = carga, positivo = descarga).

    Define únicamente la *forma* del servicio del día; el balance energético
    (carga = descarga) y el escalado a la energía objetivo se aplican después,
    de modo que el SoC sea exactamente la integral de la potencia.
    
    **Estrategia**: todas las descargas ocurren en 20-24h (sin PV), minimizando solapamiento POI.
    """
    p = np.zeros_like(h)

    if service == "Arbitraje":
        # Carga valle nocturno (00-05h), descarga noche sin PV (20-24h).
        p = np.where(h < 5.0, -1.5, p)
        p = np.where(h >= 20.0, 2.0, p)

    elif service == "Arbitraje + secundaria":
        # Carga nocturna + descarga en 20-24h, con modulación menor en día.
        p = np.where(h < 5.0, -1.5, p)
        p = np.where(h >= 20.0, 2.0, p)
        # Oscilación muy suave en 12-18h (no conflictúa con descarga)
        band = (h >= 12.0) & (h < 18.0)
        p = p + band * 0.15 * np.sin(h * 4.0 + rng.uniform(0, 1))

    else:  # "Energy shifting"
        # Carga de excedente FV a mediodía (09-15h), descarga toda en noche (20-24h).
        p = np.where((h >= 9.0) & (h < 15.0), -1.5, p)
        p = np.where(h >= 20.0, 1.5, p)

    return p


def _showcase_day_power_shape(h: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Perfil intradía del caso de uso multiservicio (figura de referencia).

    Define la *forma* de las 5 fases del día (negativo = carga, positivo =
    descarga). El balance (carga = descarga) y el escalado a la energía
    objetivo se aplican después, por lo que el SoC resultante es exactamente
    la integral de esta potencia (consistencia punto a punto):

      00–06h  carga de red en valle (precio bajo)
      06–14h  FV + carga de excedentes (top-up con ligero rizado solar)
            14–20h  modulación/carga suave sin exportación positiva
            18–22h  banda aFRR absorbente (sin conflicto con el POI)
            20–24h  descarga / noche (sin PV, máxima inyección)
    """
    p = np.zeros_like(h)
    # Fase 1 (00–06h): carga de red a precio bajo (valle nocturno).
    p = np.where(h < 6.0, -1.2, p)
    # Fase 2 (06–14h): FV + carga de excedentes (top-up suave con rizado solar).
    band2 = (h >= 6.0) & (h < 14.0)
    p = np.where(band2, -0.55 + 0.07 * np.sin((h - 6.0) * 1.5), p)
    # Fase 3 (14–20h): modulación suave sin exportación positiva (evitar picos POI).
    band3 = (h >= 14.0) & (h < 20.0)
    p = np.where(band3, -0.12 * np.abs(np.sin((h - 14.0) * 1.5)), p)
    # Fase 4 (18–22h): banda aFRR suave sin exportación neta antes de 20h.
    band4 = (h >= 18.0) & (h < 22.0)
    p = np.where(band4, -0.08 * np.abs(np.sin((h - 18.0) * 6.0 + rng.uniform(0.0, 1.0))), p)
    # Fase 5 (20–24h): descarga principal nocturna (sin solapamiento solar).
    p = np.where(h >= 20.0, 2.0, p)
    return p


def _balance_and_scale(power: np.ndarray, dt_h: float, target_discharge_mwh: float) -> np.ndarray:
    """Escala la potencia para que descarga = carga = energía objetivo.

    Garantiza energía neta diaria nula (el SoC vuelve a su nivel inicial cada
    día, sin deriva) y un throughput coherente con el dataset.
    """
    pos = np.clip(power, 0.0, None)
    neg = np.clip(power, None, 0.0)
    pos_area = float(pos.sum() * dt_h)
    neg_area = float(-neg.sum() * dt_h)
    if pos_area <= 1e-9 or neg_area <= 1e-9 or target_discharge_mwh <= 0:
        return np.zeros_like(power)
    # Descarga → energía objetivo; carga → misma energía (balance exacto).
    return pos * (target_discharge_mwh / pos_area) + neg * (target_discharge_mwh / neg_area)


def _limit_bess_export(
    pv_power: np.ndarray,
    bess_power: np.ndarray,
    dt_h: float,
    poi_limit_mw: float,
) -> np.ndarray:
    """Recorta solo la descarga BESS al margen instantáneo disponible en el POI.

    La carga (potencia negativa) se mantiene intacta. Con la PV ya curtailada a
    ``poi_limit_mw``, el margen de exportación restante es ``poi_limit_mw - PV``.
    """
    discharge_headroom = np.maximum(poi_limit_mw - pv_power, 0.0)
    limited = np.minimum(bess_power, discharge_headroom)

    pos = np.clip(limited, 0.0, None)
    neg = np.clip(limited, None, 0.0)
    discharge_mwh = float(pos.sum() * dt_h)
    charge_mwh = float(-neg.sum() * dt_h)
    if discharge_mwh <= 1e-9 or charge_mwh <= 1e-9:
        return limited

    # Mantiene energía diaria neta ~0 para que el SoC siga siendo la integral exacta
    # sin disparar la salvaguarda posterior.
    charge_scale = discharge_mwh / charge_mwh
    return pos + neg * charge_scale


def build_power_soc_series(
    bundle: dict,
    inputs: SimulationInputs,
    max_points: int = _MAX_SERIES_POINTS,
) -> pd.DataFrame:
    """Serie temporal continua de potencia (PV + BESS) y SoC sobre el rango.

    Modelo físicamente consistente **punto a punto**: la potencia de la BESS es
    balanceada cada día (carga = descarga) y el SoC es exactamente su integral
    acumulada (``SoC[i] − SoC[i−1] = −P[i]·Δt/Capacidad``). Al ser el balance
    diario nulo, el SoC no deriva y no necesita recortes que rompan la relación.

    Se traza una **quincena** consistente encadenando varios servicios
    (arbitraje, arbitraje + secundaria, energy shifting) y se repite a lo largo
    del rango. La PV se toma del dataset (perfiles diarios similares).

    Columnas: ``timestamp``, ``pv_mw``, ``bess_mw``, ``poi_mw`` (PV+BESS), ``soc_pct``, ``strategy``.
    """
    df = bundle.get("df")
    cols = ["timestamp", "pv_mw", "bess_mw", "poi_mw", "soc_pct", "strategy"]
    if df is None or df.empty or "timestamp" not in df:
        return pd.DataFrame(columns=cols)

    t0 = pd.Timestamp(df["timestamp"].iloc[0]).normalize()
    t1 = pd.Timestamp(df["timestamp"].iloc[-1]).normalize() + pd.Timedelta(days=1)

    # Resolución adaptativa: 5 min, degradando en rangos largos.
    span_min = max((t1 - t0).total_seconds() / 60.0, _PROFILE_STEP_MIN)
    step_min = max(_PROFILE_STEP_MIN, int(math.ceil(span_min / max_points)))
    step_min = int(math.ceil(step_min / 5.0) * 5)  # múltiplo de 5
    dt_h = step_min / 60.0

    grid = pd.date_range(start=t0, end=t1, freq=f"{step_min}min", inclusive="left")
    n = len(grid)
    if n == 0:
        return pd.DataFrame(columns=cols)

    hours = grid.hour.to_numpy() + grid.minute.to_numpy() / 60.0
    dates = grid.normalize()

    # --- PV sobre la rejilla (interpolación temporal) ---
    pv = bundle.get("pv")
    pv_grid = np.zeros(n)
    if pv is not None and not pv.empty and "p_ac_mw" in pv:
        pv_epoch = pv["timestamp"].astype("int64").to_numpy()
        grid_epoch = grid.astype("int64").to_numpy()
        pv_grid = np.interp(grid_epoch, pv_epoch, pv["p_ac_mw"].to_numpy())
    
    # --- CURTAILMENT de PV: meseta plana a 50 MW (límite nominal del POI) ---
    pv_grid = np.minimum(pv_grid, float(inputs.grid.poi_limit_mw))

    # --- Energía descargada diaria representativa (coherente con el dataset) ---
    daily_discharge = (
        df.assign(_d=df["timestamp"].dt.normalize())
        .groupby("_d")["energy_sold_mwh"].sum()
    )
    target_day = float(daily_discharge.mean()) if not daily_discharge.empty else 0.0

    capacity = max(inputs.total_capacity_mwh, 1e-6)
    soc_min = 100.0 * (1.0 - inputs.efficiency.max_dod)
    usable = max(100.0 - soc_min, 1e-6)
    base_seed = int(bundle.get("params", {}).get("seed", 42))

    # Cap del swing para que el SoC quepa en la ventana operativa (≈90% del rango)
    # sin recortes: limita la energía diaria mostrada (decisión de visualización).
    max_swing = 0.90 * usable
    max_energy = max_swing / 100.0 * capacity
    target_day = min(target_day, max_energy)

    # --- Despacho por día: quincena de servicios que se repite ---
    bess = np.zeros(n)
    strat = np.empty(n, dtype=object)
    unique_days = pd.DatetimeIndex(dates).unique()
    poi_limit_mw = float(inputs.grid.poi_limit_mw)

    for d in unique_days:
        mask = dates == d
        pv_day = pv_grid[mask]
        
        # Caso de uso multiservicio GARANTIZADO en su ventana de fechas.
        if SHOWCASE_START <= d <= SHOWCASE_END:
            rng = np.random.default_rng(base_seed * 100 + 777)
            shape = _showcase_day_power_shape(hours[mask], rng)
            bess_day = _balance_and_scale(shape, dt_h, target_day)
            bess[mask] = _limit_bess_export(pv_day, bess_day, dt_h, poi_limit_mw)
            strat[mask] = _SHOWCASE_LABEL
            continue
        
        fortnight_day = int((d - t0).days) % len(_FORTNIGHT_PLAN)
        service = _FORTNIGHT_PLAN[fortnight_day]
        # rng determinista por día-de-quincena → la quincena se repite idéntica.
        rng = np.random.default_rng(base_seed * 100 + fortnight_day)
        shape = _day_power_shape(service, hours[mask], rng)
        bess_day = _balance_and_scale(shape, dt_h, target_day)
        bess[mask] = _limit_bess_export(pv_day, bess_day, dt_h, poi_limit_mw)
        strat[mask] = service

    # --- SoC = integral acumulada exacta de la potencia (consistencia punto a punto) ---
    delta = -bess * dt_h / capacity * 100.0
    rel = np.cumsum(delta)
    span = float(rel.max() - rel.min()) if n else 0.0
    if span > usable:  # salvaguarda (no debería ocurrir tras el cap)
        rel = rel * (usable / span)
        span = usable
    # Centrar el recorrido del SoC dentro de la ventana [soc_min, 100].
    offset = soc_min + (usable - span) / 2.0 - float(rel.min())
    soc = rel + offset

    # --- Potencia real en POI = PV + BESS ---
    poi = pv_grid + bess

    return pd.DataFrame({
        "timestamp": grid,
        "pv_mw": pv_grid,
        "bess_mw": bess,
        "poi_mw": poi,
        "soc_pct": soc,
        "strategy": strat,
    })


def build_daily_production(bundle: dict, inputs: SimulationInputs) -> pd.DataFrame:
    """Agrega el dataset a producción diaria (carga/descarga y SoH).

    Columnas: ``date``, ``charge_mwh`` (negativa), ``discharge_mwh`` (positiva),
    ``soh`` (fracción).
    """
    df = bundle.get("df")
    empty = pd.DataFrame(columns=["date", "charge_mwh", "discharge_mwh", "soh"])
    if df is None or df.empty:
        return empty

    daily = df.copy()
    daily["date"] = daily["timestamp"].dt.date
    grouped = daily.groupby("date").agg(
        discharge_mwh=("energy_sold_mwh", "sum"),
        rte=("rte", "mean"),
        soh=("soh", "last"),
    ).reset_index()
    grouped["charge_mwh"] = -(grouped["discharge_mwh"] / grouped["rte"].where(grouped["rte"] > 0, np.nan))
    grouped["charge_mwh"] = grouped["charge_mwh"].fillna(0.0)
    return grouped[["date", "charge_mwh", "discharge_mwh", "soh"]]
