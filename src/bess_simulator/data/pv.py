"""Generador de generación fotovoltaica sintética (Fase 3).

Toma el dataset meteorológico (Fase 2) y produce la generación de la planta PV
a resolución 15 minutos, conforme al contrato :data:`PV_COLUMNS`.

Cadena de cálculo:
  1. POA = irradiancia efectiva final en el colector (= GHI del dataset meteo;
     no se modela transposición GHI→POA en esta fase de alcance).
  2. Temperatura de célula por modelo NOCT:
        T_cell = T_amb + (NOCT − 20)/800 · POA
  3. Potencia DC:
        P_dc = MWp · (POA/1000) · (1 + γ·(T_cell − 25)) · PR · (1 − soiling)
               · (1 − dc_losses) · (1 − degradación_anual·años)
  4. Potencia AC con clipping del inversor:
        P_ac = min(P_dc · η_inv, inverter_ac_mw)
        P_clipped = max(P_dc · η_inv − inverter_ac_mw, 0)

Referencias:
  - NOCT/Sandia cell temperature model.
  - Coef. temperatura c-Si: ~−0.35%/°C (γ = −0.0035 1/°C).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bess_simulator.models.parameters import PvParams
from bess_simulator.models.topology import (
    PV_COLUMNS,
    empty_pv_frame,
    validate_columns,
)

_STC_IRRADIANCE = 1000.0  # W/m² (Standard Test Conditions)
_STC_TEMP = 25.0          # °C
_NOCT_REF_IRRADIANCE = 800.0
_NOCT_REF_TEMP = 20.0


def _cell_temperature(poa: np.ndarray, temp_ambient: np.ndarray, noct: float) -> np.ndarray:
    return temp_ambient + (noct - _NOCT_REF_TEMP) / _NOCT_REF_IRRADIANCE * poa


def generate_pv_dataset(
    meteo_df: pd.DataFrame,
    pv: PvParams,
    cfg: dict,
) -> pd.DataFrame:
    """Genera la serie de generación PV a partir del dataset meteorológico.

    ``meteo_df`` debe cumplir el contrato METEO_COLUMNS (al menos timestamp,
    ``ghi`` y ``temp_ambient``). Devuelve un DataFrame conforme a PV_COLUMNS.
    """
    if meteo_df.empty:
        return empty_pv_frame()

    timestamps = pd.DatetimeIndex(meteo_df["timestamp"].to_numpy())
    poa = meteo_df["ghi"].to_numpy()  # POA = irradiancia efectiva final
    temp_ambient = meteo_df["temp_ambient"].to_numpy()

    temp_cell = _cell_temperature(poa, temp_ambient, cfg["pv_noct"])

    # Antigüedad en años desde el inicio de la serie (degradación lineal).
    years = (timestamps - timestamps[0]).total_seconds().to_numpy() / (365.0 * 86400.0)
    degradation_factor = np.clip(1.0 - pv.annual_degradation * years, 0.0, 1.0)

    temp_factor = 1.0 + cfg["pv_temp_coeff_pmax"] * (temp_cell - _STC_TEMP)

    p_dc_mw = (
        pv.peak_power_mwp
        * (poa / _STC_IRRADIANCE)
        * temp_factor
        * pv.performance_ratio
        * (1.0 - pv.soiling_loss)
        * (1.0 - cfg["pv_dc_losses"])
        * degradation_factor
    )
    p_dc_mw = np.clip(p_dc_mw, 0.0, None)

    p_ac_pre = p_dc_mw * cfg["pv_inverter_efficiency"]
    p_ac_mw = np.minimum(p_ac_pre, pv.inverter_ac_mw)
    p_clipped_mw = np.clip(p_ac_pre - pv.inverter_ac_mw, 0.0, None)

    df = pd.DataFrame({
        "timestamp": timestamps,
        "poa": poa,
        "temp_cell": temp_cell,
        "p_dc_mw": p_dc_mw,
        "p_ac_mw": p_ac_mw,
        "p_clipped_mw": p_clipped_mw,
    })
    validate_columns(df, PV_COLUMNS)
    return df[list(PV_COLUMNS.keys())]
