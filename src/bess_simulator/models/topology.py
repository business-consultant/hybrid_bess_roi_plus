"""Contrato de datos de la planta híbrida PV + BESS.

Fuente única de verdad de la **topología de flujos energéticos** y del esquema
de columnas que los generadores (PV, despacho) deben producir. No contiene
lógica de cálculo: solo define el contrato que las Fases 3 (generación PV) y 5
(motor de despacho) deben respetar.

Topología de flujos (resolución 15 min):

    PV ──┬──▶ red            (pv_to_grid)
         ├──▶ BESS           (pv_to_bess)   ← recupera clipping/curtailment
         └──▶ curtailment    (pv_curtailed)

    red ─────▶ BESS          (grid_to_bess) ← carga desde red (arbitraje)
    BESS ────▶ red           (bess_to_grid) ← descarga (arbitraje + servicios)

    POI (punto de interconexión, límite compartido):
        flujo_neto = pv_to_grid + bess_to_grid − grid_to_bess   ≤  poi_limit_mw
"""

from __future__ import annotations

import pandas as pd


# --- Columnas del dataset meteorológico (Fase 2) ---
METEO_COLUMNS: dict[str, str] = {
    "timestamp": "datetime64[ns]",
    "solar_elevation": "float64",  # elevación solar (grados, <0 de noche)
    "ghi": "float64",            # irradiancia global horizontal (W/m²)
    "ghi_clearsky": "float64",   # irradiancia de cielo claro (W/m²)
    "clearness_index": "float64",  # kt = ghi / ghi_clearsky (0..1)
    "temp_ambient": "float64",   # temperatura ambiente (°C)
    "wind_speed": "float64",     # velocidad de viento (m/s)
    "humidity": "float64",       # humedad relativa (0..1)
}

# --- Columnas del dataset de generación PV (Fase 3) ---
PV_COLUMNS: dict[str, str] = {
    "timestamp": "datetime64[ns]",
    "poa": "float64",            # irradiancia efectiva final en el colector (W/m²)
    "temp_cell": "float64",      # temperatura de célula (°C)
    "p_dc_mw": "float64",        # potencia DC antes del inversor (MW)
    "p_ac_mw": "float64",        # potencia AC tras inversor, post-clipping (MW)
    "p_clipped_mw": "float64",   # potencia recortada por el inversor (MW)
}

# --- Columnas de flujos de la planta híbrida (Fase 5) ---
HYBRID_FLOW_COLUMNS: dict[str, str] = {
    "timestamp": "datetime64[ns]",
    "pv_to_grid": "float64",     # energía PV inyectada a red (MWh)
    "pv_to_bess": "float64",     # energía PV almacenada en BESS (MWh)
    "pv_curtailed": "float64",   # energía PV recortada por límite POI (MWh)
    "grid_to_bess": "float64",   # energía de red a BESS (MWh)
    "bess_to_grid": "float64",   # energía BESS a red (MWh)
    "poi_net_mw": "float64",     # flujo neto en el POI (MW, + export / − import)
    "poi_curtailed": "float64",  # energía recortada por restricción POI (MWh)
}

# --- Columnas de ingresos por stream (Fase 5) ---
REVENUE_STREAM_COLUMNS: dict[str, str] = {
    "income_arbitrage": "float64",   # ingresos por arbitraje (€)
    "income_ppa": "float64",         # ingresos PPA precio fijo (€)
    "income_capacity": "float64",    # ingresos por pago de capacidad (€)
    "income_secondary": "float64",   # ingresos por regulación secundaria (€)
}


def empty_meteo_frame() -> pd.DataFrame:
    return _empty_frame(METEO_COLUMNS)


def empty_pv_frame() -> pd.DataFrame:
    return _empty_frame(PV_COLUMNS)


def empty_hybrid_flow_frame() -> pd.DataFrame:
    return _empty_frame(HYBRID_FLOW_COLUMNS)


def validate_columns(df: pd.DataFrame, schema: dict[str, str]) -> None:
    """Comprueba que ``df`` contiene todas las columnas del esquema.

    Lanza ``ValueError`` si falta alguna columna requerida.
    """
    missing = [col for col in schema if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en el contrato: {missing}")


def _empty_frame(schema: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in schema.items()})
