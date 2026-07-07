"""Tests del registro de eventos críticos (APM) y la inyección de anomalías."""

import numpy as np
import pandas as pd
import pytest

from bess_simulator.recommendations.alarms import (
    Alarm,
    CATEGORY_SAFETY,
    CATEGORY_HEALTH,
    CATEGORY_WARRANTY,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    check_historical_alarms,
    generate_alarm_message,
)
from bess_simulator.data.synthetic import generate_dashboard_dataset
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG


def _df(temperature=None, rte=None, soh=None, n=8):
    ts = pd.date_range("2025-01-01", periods=n, freq="15min")
    data = {"timestamp": ts}
    if temperature is not None:
        data["temperature"] = temperature
    if rte is not None:
        data["rte"] = rte
    if soh is not None:
        data["soh"] = soh
    return pd.DataFrame(data)


class TestRegistryDetection:
    def test_temperature_event_is_safety_critical(self):
        temp = [20, 20, 45, 48, 20, 20, 20, 20]
        alarms = check_historical_alarms(_df(temperature=temp), cfg={"alarm_temp_critical_c": 40.0})
        assert len(alarms) == 1
        a = alarms[0]
        assert a.parameter == "Temperatura"
        assert a.category == CATEGORY_SAFETY
        assert a.severity == SEVERITY_CRITICAL
        assert a.count == 2
        assert a.worst_value == 48
        assert a.subelement

    def test_rte_event_is_warranty_warning(self):
        rte = [0.85, 0.70, 0.72, 0.85, 0.85, 0.85, 0.85, 0.85]
        alarms = check_historical_alarms(_df(rte=rte), cfg={"alarm_rte_min": 0.78})
        assert len(alarms) == 1
        a = alarms[0]
        assert a.parameter == "RTE"
        assert a.category == CATEGORY_WARRANTY
        assert a.severity == SEVERITY_WARNING
        assert a.count == 2
        assert a.worst_value == pytest.approx(0.70)

    def test_soh_event_is_health_critical(self):
        soh = [0.95, 0.95, 0.79, 0.78, 0.95, 0.95, 0.95, 0.95]
        alarms = check_historical_alarms(_df(soh=soh), cfg={"alarm_soh_min": 0.80})
        assert len(alarms) == 1
        a = alarms[0]
        assert a.parameter == "SoH"
        assert a.category == CATEGORY_HEALTH
        assert a.severity == SEVERITY_CRITICAL
        assert a.count == 2

    def test_no_events_when_in_range(self):
        alarms = check_historical_alarms(
            _df(temperature=[20] * 8, rte=[0.85] * 8, soh=[0.95] * 8),
            cfg={"alarm_temp_critical_c": 40.0, "alarm_rte_min": 0.78, "alarm_soh_min": 0.80},
        )
        assert alarms == []

    def test_first_and_last_timestamp(self):
        temp = [20, 45, 20, 20, 20, 20, 46, 20]
        alarms = check_historical_alarms(_df(temperature=temp), cfg={"alarm_temp_critical_c": 40.0})
        a = alarms[0]
        assert a.first_timestamp == pd.Timestamp("2025-01-01 00:15:00")
        assert a.last_timestamp == pd.Timestamp("2025-01-01 01:30:00")

    def test_empty_dataframe_safe(self):
        assert check_historical_alarms(pd.DataFrame()) == []
        assert check_historical_alarms(None) == []

    def test_partial_columns_backward_compatible(self):
        # El motor de simulación solo aporta RTE: debe funcionar igual.
        alarms = check_historical_alarms(_df(rte=[0.70] * 4, n=4), cfg={"alarm_rte_min": 0.78})
        assert len(alarms) == 1
        assert alarms[0].parameter == "RTE"

    def test_multiple_categories(self):
        df = _df(
            temperature=[20, 45, 20, 20, 20, 20, 20, 20],
            rte=[0.85, 0.85, 0.70, 0.85, 0.85, 0.85, 0.85, 0.85],
            soh=[0.95, 0.95, 0.95, 0.79, 0.95, 0.95, 0.95, 0.95],
        )
        alarms = check_historical_alarms(df, cfg=DEFAULT_ADVANCED_CONFIG)
        params = {a.parameter for a in alarms}
        assert params == {"Temperatura", "RTE", "SoH"}


class TestAlarmMessage:
    def test_empty(self):
        assert generate_alarm_message([]) == ""

    def test_lists_parameters(self):
        msg = generate_alarm_message([
            Alarm("Temperatura", "x"), Alarm("RTE", "y"),
        ])
        assert "Temperatura" in msg and "RTE" in msg


class TestAnomalyInjection:
    def test_injection_creates_events(self):
        df = generate_dashboard_dataset(seed=42)
        hist = df[~df["is_forecast"]]
        alarms = check_historical_alarms(hist, cfg=DEFAULT_ADVANCED_CONFIG)
        params = {a.parameter for a in alarms}
        # Con la inyección por defecto debe haber al menos eventos de Temperatura y RTE.
        assert "Temperatura" in params
        assert "RTE" in params

    def test_injection_is_deterministic(self):
        a = generate_dashboard_dataset(seed=7)
        b = generate_dashboard_dataset(seed=7)
        assert a["temperature"].equals(b["temperature"])
        assert a["rte"].equals(b["rte"])

    def test_disable_injection_reduces_extremes(self):
        cfg_off = dict(DEFAULT_ADVANCED_CONFIG)
        cfg_off["anomaly_enable"] = False
        df_off = generate_dashboard_dataset(seed=42, advanced_config=cfg_off)
        df_on = generate_dashboard_dataset(seed=42, advanced_config=DEFAULT_ADVANCED_CONFIG)
        hist_off = df_off[~df_off["is_forecast"]]
        hist_on = df_on[~df_on["is_forecast"]]
        # Sin inyección, el RTE nunca cae tan abajo como con ella.
        assert hist_off["rte"].min() > hist_on["rte"].min()
        assert hist_off["temperature"].max() < hist_on["temperature"].max()
