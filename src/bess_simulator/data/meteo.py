"""Generador meteorológico sintético (Fase 2).

Capa física base de la planta híbrida: produce el recurso meteorológico
(irradiancia, temperatura, viento, humedad) que alimenta tanto la generación
PV (Fase 3) como la monitorización de subelementos (Fase 7).

Modelo:
  - Geometría solar por declinación y ángulo horario → elevación solar.
  - Irradiancia de cielo claro (Haurwitz) a partir de la elevación.
  - Nubosidad mediante clearness index kt con persistencia AR(1)
    (los días nublados se agrupan; no es ruido blanco).
  - Temperatura ambiente estacional + diaria + ruido.
  - Viento (AR(1)) y humedad acoplada inversamente a la irradiancia.

Referencias:
  - Haurwitz (1945): GHI_cs ≈ 1098·sin(α)·exp(−0.059/sin(α)) W/m².
  - Clearness index kt: Liu & Jordan; persistencia tipo Markov en series
    horarias de irradiancia (autocorrelación elevada intradía).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bess_simulator.config import INTERVALS_PER_DAY
from bess_simulator.models.topology import METEO_COLUMNS, empty_meteo_frame

# Constante de Haurwitz para irradiancia de cielo claro.
_HAURWITZ_A = 1098.0
_HAURWITZ_B = 0.059


def _solar_elevation(timestamps: pd.DatetimeIndex, latitude_deg: float) -> np.ndarray:
    """Elevación solar (grados) por geometría declinación / ángulo horario.

    Usa tiempo solar aproximado (sin corrección de longitud ni ecuación del
    tiempo), suficiente para datos sintéticos.
    """
    n = timestamps.dayofyear.to_numpy()
    hour = timestamps.hour.to_numpy() + timestamps.minute.to_numpy() / 60.0

    lat = np.radians(latitude_deg)
    decl = np.radians(23.45 * np.sin(np.radians(360.0 * (284 + n) / 365.0)))
    hour_angle = np.radians(15.0 * (hour - 12.0))

    sin_elev = (
        np.sin(lat) * np.sin(decl)
        + np.cos(lat) * np.cos(decl) * np.cos(hour_angle)
    )
    sin_elev = np.clip(sin_elev, -1.0, 1.0)
    return np.degrees(np.arcsin(sin_elev))


def _clearsky_ghi(elevation_deg: np.ndarray) -> np.ndarray:
    """Irradiancia global horizontal de cielo claro (W/m²) — modelo Haurwitz."""
    sin_elev = np.sin(np.radians(elevation_deg))
    ghi = np.zeros_like(sin_elev)
    day = sin_elev > 0.0
    ghi[day] = _HAURWITZ_A * sin_elev[day] * np.exp(-_HAURWITZ_B / sin_elev[day])
    return np.clip(ghi, 0.0, None)


def _clearness_series(n: int, rng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Serie de clearness index kt con persistencia AR(1)."""
    mean = cfg["meteo_kt_mean"]
    ar = cfg["meteo_kt_ar"]
    noise_std = cfg["meteo_kt_noise_std"]
    kt_min, kt_max = cfg["meteo_kt_min"], cfg["meteo_kt_max"]

    kt = np.empty(n)
    kt[0] = mean
    noise = rng.normal(0.0, noise_std, n)
    for i in range(1, n):
        kt[i] = mean + ar * (kt[i - 1] - mean) + noise[i]
    return np.clip(kt, kt_min, kt_max)


def _ambient_temperature(
    timestamps: pd.DatetimeIndex, rng: np.random.Generator, cfg: dict
) -> np.ndarray:
    day_of_year = timestamps.dayofyear.to_numpy()
    hour = timestamps.hour.to_numpy() + timestamps.minute.to_numpy() / 60.0

    seasonal = cfg["meteo_temp_mean"] + cfg["meteo_temp_seasonal_amp"] * np.sin(
        (day_of_year - 80) * 2 * np.pi / 365.0
    )
    daily = cfg["meteo_temp_daily_amp"] * np.sin((hour - 9.0) * np.pi / 12.0)
    noise = rng.normal(0.0, cfg["meteo_temp_noise_std"], len(timestamps))
    return seasonal + daily + noise


def _wind_series(n: int, rng: np.random.Generator, cfg: dict) -> np.ndarray:
    mean = cfg["meteo_wind_mean"]
    std = cfg["meteo_wind_std"]
    wind = np.empty(n)
    wind[0] = mean
    noise = rng.normal(0.0, std, n)
    for i in range(1, n):
        wind[i] = mean + 0.85 * (wind[i - 1] - mean) + 0.5 * noise[i]
    return np.clip(wind, 0.0, None)


def generate_meteo_dataset(
    start_date: str,
    end_date: str,
    latitude: float,
    cfg: dict,
    seed: int | None = None,
) -> pd.DataFrame:
    """Genera el dataset meteorológico sintético a resolución 15 minutos.

    Devuelve un DataFrame conforme al contrato :data:`METEO_COLUMNS`.
    """
    timestamps = pd.date_range(start=start_date, end=end_date, freq="15min", inclusive="left")
    n = len(timestamps)
    if n == 0:
        return empty_meteo_frame()

    rng = np.random.default_rng(seed)

    elevation = _solar_elevation(timestamps, latitude)
    ghi_cs = _clearsky_ghi(elevation)
    kt = _clearness_series(n, rng, cfg)
    ghi = ghi_cs * kt

    temp_ambient = _ambient_temperature(timestamps, rng, cfg)
    wind = _wind_series(n, rng, cfg)

    cloudiness = 1.0 - kt
    humidity = np.clip(
        cfg["meteo_humidity_mean"]
        + cfg["meteo_humidity_cloud_coupling"] * (cloudiness - 0.30)
        + rng.normal(0.0, 0.05, n),
        0.0, 1.0,
    )

    df = pd.DataFrame({
        "timestamp": timestamps,
        "solar_elevation": elevation,
        "ghi": ghi,
        "ghi_clearsky": ghi_cs,
        "clearness_index": kt,
        "temp_ambient": temp_ambient,
        "wind_speed": wind,
        "humidity": humidity,
    })
    return df[list(METEO_COLUMNS.keys())]
