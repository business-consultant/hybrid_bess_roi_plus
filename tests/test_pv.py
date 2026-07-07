import numpy as np
import pandas as pd
import pytest

from bess_simulator.data.meteo import generate_meteo_dataset
from bess_simulator.data.pv import generate_pv_dataset
from bess_simulator.models.parameters import PvParams
from bess_simulator.models.topology import PV_COLUMNS, validate_columns
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG

CFG = DEFAULT_ADVANCED_CONFIG


def _meteo(start="2025-06-01", end="2025-06-08", lat=40.0, seed=42):
    return generate_meteo_dataset(start, end, latitude=lat, cfg=CFG, seed=seed)


def _pv(meteo=None, pv=None):
    return generate_pv_dataset(meteo if meteo is not None else _meteo(), pv or PvParams(), CFG)


def test_columns_match_contract():
    df = _pv()
    validate_columns(df, PV_COLUMNS)
    assert list(df.columns) == list(PV_COLUMNS.keys())


def test_empty_meteo_returns_empty_frame():
    empty = _meteo("2025-06-08", "2025-06-01")
    df = generate_pv_dataset(empty, PvParams(), CFG)
    assert df.empty
    assert list(df.columns) == list(PV_COLUMNS.keys())


def test_no_generation_at_night():
    df = _pv().set_index("timestamp")
    night = df.between_time("00:00", "00:15")
    assert (night["p_dc_mw"] == 0).all()
    assert (night["p_ac_mw"] == 0).all()


def test_generation_at_noon():
    df = _pv().set_index("timestamp")
    noon = df.between_time("12:00", "13:00")
    assert noon["p_ac_mw"].mean() > 0


def test_ac_never_exceeds_inverter_rating():
    pv = PvParams()
    df = _pv(pv=pv)
    assert (df["p_ac_mw"] <= pv.inverter_ac_mw + 1e-9).all()


def test_clipping_occurs_with_high_ilr():
    # ILR alto fuerza clipping en horas de alta irradiancia
    pv = PvParams(peak_power_mwp=100.0, inverter_ac_mw=40.0)
    df = _pv(pv=pv)
    assert df["p_clipped_mw"].max() > 0


def test_no_clipping_when_inverter_oversized():
    pv = PvParams(peak_power_mwp=40.0, inverter_ac_mw=100.0)
    df = _pv(pv=pv)
    assert df["p_clipped_mw"].max() == 0


def test_cell_temp_above_ambient_in_sun():
    meteo = _meteo()
    df = generate_pv_dataset(meteo, PvParams(), CFG)
    merged = df.merge(meteo[["timestamp", "ghi", "temp_ambient"]], on="timestamp")
    sunny = merged[merged["ghi"] > 200]
    assert (sunny["temp_cell"] > sunny["temp_ambient"]).all()


def test_degradation_reduces_output_over_years():
    meteo = generate_meteo_dataset("2025-06-01", "2035-06-01", latitude=40.0, cfg=CFG, seed=1)
    df = generate_pv_dataset(meteo, PvParams(), CFG).set_index("timestamp")
    first_june = df.loc["2025-06"]["p_ac_mw"].sum()
    last_june = df.loc["2034-06"]["p_ac_mw"].sum()
    assert last_june < first_june


def test_higher_soiling_reduces_output():
    meteo = _meteo()
    clean = generate_pv_dataset(meteo, PvParams(soiling_loss=0.0), CFG)["p_ac_mw"].sum()
    dirty = generate_pv_dataset(meteo, PvParams(soiling_loss=0.10), CFG)["p_ac_mw"].sum()
    assert dirty < clean
