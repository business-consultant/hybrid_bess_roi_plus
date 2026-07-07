from datetime import date

import numpy as np
import pandas as pd
import pytest

from bess_simulator.data.meteo import generate_meteo_dataset
from bess_simulator.models.topology import METEO_COLUMNS, validate_columns
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG

CFG = DEFAULT_ADVANCED_CONFIG


def _gen(start="2025-06-01", end="2025-06-08", lat=40.0, seed=42):
    return generate_meteo_dataset(start, end, latitude=lat, cfg=CFG, seed=seed)


def test_columns_match_contract():
    df = _gen()
    validate_columns(df, METEO_COLUMNS)
    assert list(df.columns) == list(METEO_COLUMNS.keys())


def test_empty_range_returns_empty_frame():
    df = generate_meteo_dataset("2025-06-08", "2025-06-01", latitude=40.0, cfg=CFG, seed=1)
    assert df.empty
    assert list(df.columns) == list(METEO_COLUMNS.keys())


def test_ghi_zero_at_night_positive_at_noon():
    df = _gen()
    df = df.set_index("timestamp")
    # Medianoche: sol bajo el horizonte → GHI 0
    midnight = df.between_time("00:00", "00:15")
    assert (midnight["ghi"] == 0).all()
    # Mediodía en junio en latitud 40 → GHI claramente positiva
    noon = df.between_time("12:00", "13:00")
    assert noon["ghi"].mean() > 300


def test_clearness_index_within_bounds():
    df = _gen()
    assert df["clearness_index"].between(CFG["meteo_kt_min"], CFG["meteo_kt_max"]).all()


def test_ghi_never_exceeds_clearsky():
    df = _gen()
    assert (df["ghi"] <= df["ghi_clearsky"] + 1e-9).all()


def test_humidity_in_unit_interval():
    df = _gen()
    assert df["humidity"].between(0.0, 1.0).all()


def test_wind_non_negative():
    df = _gen()
    assert (df["wind_speed"] >= 0).all()


def test_reproducible_with_seed():
    a = _gen(seed=7)
    b = _gen(seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_clearness_is_persistent_not_white_noise():
    # La autocorrelación lag-1 debe ser alta (persistencia AR(1))
    df = _gen(start="2025-06-01", end="2025-07-01")
    kt = df["clearness_index"].to_numpy()
    autocorr = np.corrcoef(kt[:-1], kt[1:])[0, 1]
    assert autocorr > 0.5


def test_higher_latitude_lower_noon_elevation():
    low = _gen(lat=20.0).set_index("timestamp").between_time("12:00", "12:15")
    high = _gen(lat=60.0).set_index("timestamp").between_time("12:00", "12:15")
    assert low["solar_elevation"].mean() > high["solar_elevation"].mean()
