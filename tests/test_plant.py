"""Tests de la Fase 6: resumen de planta híbrida y perfiles de la pantalla general."""

import numpy as np
import pandas as pd
import pytest

from bess_simulator.models.parameters import SimulationInputs, PvParams, GridParams
from bess_simulator.config import INTERVAL_DURATION_H
from bess_simulator.engine.plant import (
    compute_plant_summary,
    compute_kpi_deviations,
    compute_pv_kpi_deviations,
    build_power_soc_series,
    build_daily_production,
    slice_bundle,
    SHOWCASE_START,
    SHOWCASE_END,
)
from bess_simulator.data.meteo import generate_meteo_dataset
from bess_simulator.data.pv import generate_pv_dataset
from bess_simulator.data.synthetic import generate_dashboard_dataset
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG


def _make_bundle():
    start, hoy, end = "2025-01-01", "2025-04-01", "2025-07-01"
    df = generate_dashboard_dataset(
        start_date=start, hoy=hoy, end_date=end,
        rated_power_mw=50, c_rate_inverse=4, seed=42,
    )
    meteo = generate_meteo_dataset(start, end, latitude=40.0,
                                   cfg=DEFAULT_ADVANCED_CONFIG, seed=42)
    pv = generate_pv_dataset(meteo, PvParams(), DEFAULT_ADVANCED_CONFIG)
    return {
        "df": df, "meteo": meteo, "pv": pv,
        "start": start, "hoy": hoy, "end": end,
        "params": {"rated_power_mw": 50, "c_rate_inverse": 4, "latitude": 40.0},
        "label": "test",
    }


class TestPlantSummary:
    def test_specs_from_inputs(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        assert s.nominal_power_mw == inputs.output_power_mw
        assert s.bess_capacity_mwh == inputs.total_capacity_mwh
        assert s.pv_peak_mwp == inputs.pv.peak_power_mwp
        assert s.ilr == inputs.pv.dc_ac_ratio

    def test_energy_delivered_positive(self):
        bundle = _make_bundle()
        s = compute_plant_summary(bundle, SimulationInputs())
        assert s.exported_gwh > 0
        assert s.imported_gwh > 0
        assert s.pv_generated_gwh > 0
        # Importada = descarga / rte → mayor que la energía descargada sola.
        assert s.exported_pct + s.imported_pct == pytest.approx(100.0)

    def test_kpis_in_range(self):
        bundle = _make_bundle()
        s = compute_plant_summary(bundle, SimulationInputs())
        assert 0 <= s.time_based_availability <= 100
        assert 0 < s.roundtrip_efficiency < 1
        assert 0 < s.state_of_health <= 1
        assert s.cycle_count > 0
        assert s.charge_discharge_avg_power_mw > 0
        assert s.soc_min_pct >= 0

    def test_soc_window_from_dod(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        inputs.efficiency.max_dod = 0.9
        s = compute_plant_summary(bundle, inputs)
        assert s.soc_min_pct == pytest.approx(10.0)
        assert s.soc_max_pct == 100.0

    def test_subelement_counts_scale(self):
        bundle = _make_bundle()
        small = SimulationInputs()
        small.bess.rated_power_mw = 10
        big = SimulationInputs()
        big.bess.rated_power_mw = 100
        s_small = compute_plant_summary(bundle, small)
        s_big = compute_plant_summary(bundle, big)
        assert s_big.pcs > s_small.pcs
        assert s_small.meters == 1

    def test_empty_dataset_safe(self):
        s = compute_plant_summary({"df": pd.DataFrame(), "pv": pd.DataFrame()},
                                  SimulationInputs())
        assert s.exported_gwh == 0
        assert s.cycle_count == 0


class TestPowerSocSeries:
    def test_series_columns_and_nonempty(self):
        bundle = _make_bundle()
        s = build_power_soc_series(bundle, SimulationInputs())
        assert not s.empty
        assert {"timestamp", "pv_mw", "bess_mw", "soc_pct", "strategy"} <= set(s.columns)

    def test_series_charges_and_discharges(self):
        bundle = _make_bundle()
        s = build_power_soc_series(bundle, SimulationInputs())
        assert (s["bess_mw"] < 0).any()  # carga
        assert (s["bess_mw"] > 0).any()  # descarga

    def test_series_soc_within_window(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        soc_min = 100.0 * (1.0 - inputs.efficiency.max_dod)
        assert s["soc_pct"].min() >= soc_min - 1e-6
        assert s["soc_pct"].max() <= 100.0 + 1e-6

    def test_series_chains_multiple_strategies(self):
        bundle = _make_bundle()  # ~6 meses → varios días → varias estrategias
        s = build_power_soc_series(bundle, SimulationInputs())
        assert s["strategy"].nunique() >= 2

    def test_series_soc_is_exact_power_integral(self):
        """Consistencia punto a punto: ΔSoC[i] = −P[i]·Δt/Capacidad·100."""
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        ts = s["timestamp"].to_numpy()
        dt_h = (ts[1] - ts[0]) / np.timedelta64(1, "h")
        capacity = inputs.total_capacity_mwh
        expected_delta = -s["bess_mw"].to_numpy() * dt_h / capacity * 100.0
        actual_delta = np.diff(s["soc_pct"].to_numpy())
        # La relación se cumple en TODOS los puntos (no solo a fin de ciclo).
        assert np.allclose(actual_delta, expected_delta[1:], atol=1e-6)

    def test_series_daily_energy_balanced(self):
        """Cada día carga ≈ descarga → el SoC no deriva (balance energético)."""
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        ts = s["timestamp"].to_numpy()
        dt_h = (ts[1] - ts[0]) / np.timedelta64(1, "h")
        p = s["bess_mw"].to_numpy()
        charge = -np.clip(p, None, 0).sum() * dt_h
        discharge = np.clip(p, 0, None).sum() * dt_h
        assert charge == pytest.approx(discharge, rel=0.02)

    def test_showcase_window_is_guaranteed(self):
        """Las fechas del caso de uso muestran su etiqueta y las 5 fases."""
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        show = s[
            (s["timestamp"] >= SHOWCASE_START)
            & (s["timestamp"] < SHOWCASE_END + pd.Timedelta(days=1))
        ]
        # Todos los puntos de la ventana llevan la etiqueta del caso de uso.
        assert not show.empty
        assert (show["strategy"] == "Caso de uso multiservicio").all()
        # 5 días reproducibles: cada día está balanceado (neto ≈ 0) y descarga
        # una energía similar (misma magnitud de caso de uso).
        ts = s["timestamp"].to_numpy()
        dt_h = (ts[1] - ts[0]) / np.timedelta64(1, "h")
        per_day = show.assign(_d=show["timestamp"].dt.normalize()).groupby("_d")
        discharges = []
        for _, g in per_day:
            p = g["bess_mw"].to_numpy()
            net = p.sum() * dt_h
            disch = np.clip(p, 0, None).sum() * dt_h
            assert abs(net) < 0.05 * max(disch, 1e-6)   # balanceado (neto ~0)
            discharges.append(disch)
        assert len(discharges) == 5
        assert np.std(discharges) < 0.1 * np.mean(discharges)   # magnitud estable

    def test_showcase_phases_charge_then_discharge(self):
        """Caso de uso: carga diurna y exportación positiva solo en la noche."""
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        day = s[s["timestamp"].dt.normalize() == SHOWCASE_START]
        h = day["timestamp"].dt.hour.to_numpy()
        p = day["bess_mw"].to_numpy()
        # Fase 1-2 (madrugada/mañana) carga neta; no hay export positivo antes de 20h.
        assert p[h < 6].mean() < 0          # carga de red
        assert p[(h >= 14) & (h < 20)].max() <= 1e-6
        assert p[h >= 20].mean() > 0        # descarga nocturna

    def test_series_pv_positive_daytime(self):
        bundle = _make_bundle()
        s = build_power_soc_series(bundle, SimulationInputs())
        assert s["pv_mw"].max() > 0

    def test_series_pv_is_curtailed_at_poi_limit(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        assert s["pv_mw"].max() <= inputs.grid.poi_limit_mw + 1e-6

    def test_series_poi_never_exceeds_limit(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = build_power_soc_series(bundle, inputs)
        assert s["poi_mw"].max() <= inputs.grid.poi_limit_mw + 1e-6

    def test_series_respects_max_points(self):
        bundle = _make_bundle()
        s = build_power_soc_series(bundle, SimulationInputs(), max_points=500)
        assert len(s) <= 500 + 1

    def test_daily_production_signs(self):
        bundle = _make_bundle()
        daily = build_daily_production(bundle, SimulationInputs())
        assert not daily.empty
        assert (daily["discharge_mwh"] >= 0).all()
        assert (daily["charge_mwh"] <= 0).all()


class TestSliceBundle:
    def test_slice_filters_range(self):
        bundle = _make_bundle()
        sliced = slice_bundle(bundle, "2025-02-01", "2025-02-28")
        assert not sliced["df"].empty
        assert sliced["df"]["timestamp"].min() >= pd.Timestamp("2025-02-01")
        assert sliced["df"]["timestamp"].max() < pd.Timestamp("2025-03-01")
        # No muta el bundle original.
        assert len(bundle["df"]) > len(sliced["df"])

    def test_slice_summary_consistent(self):
        bundle = _make_bundle()
        sliced = slice_bundle(bundle, "2025-02-01", "2025-02-28")
        s = compute_plant_summary(sliced, SimulationInputs())
        assert s.exported_gwh > 0
        assert s.cycle_count > 0


class TestKpiDeviations:
    def test_deviation_keys_and_signs(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        devs = compute_kpi_deviations(s, inputs, n_days=180)
        assert {"availability", "soc_range", "rte", "cycles", "soh", "avg_power"} == set(devs)
        for v in devs.values():
            assert isinstance(v, float)

    def test_availability_deviation_value(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        devs = compute_kpi_deviations(s, inputs, n_days=180)
        expected = (s.time_based_availability - 98.0) / 98.0 * 100.0
        assert devs["availability"] == pytest.approx(expected)


class TestPvKpis:
    """KPIs fotovoltaicos: fórmulas estándar de negocio (IEC 61724)."""

    def test_pv_kpis_in_range(self):
        bundle = _make_bundle()
        s = compute_plant_summary(bundle, SimulationInputs())
        # Capacity factor de una planta FV en latitud media: rango razonable.
        assert 0.0 < s.pv_capacity_factor < 0.5
        # Performance ratio estándar (con pérdidas) por debajo de 1.
        assert 0.5 < s.pv_performance_ratio < 1.0
        assert 0.0 <= s.pv_availability <= 100.0
        assert s.pv_irradiation_wh_m2 > 0.0
        assert s.pv_production_mwh > 0.0
        assert s.pv_clearsky_wh_m2 >= s.pv_irradiation_wh_m2  # cielo claro = potencial

    def test_capacity_factor_formula_ac_base(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        pv_hours = len(bundle["pv"]) * INTERVAL_DURATION_H
        expected_cf = s.pv_production_mwh / (inputs.pv.inverter_ac_mw * pv_hours)
        assert s.pv_capacity_factor == pytest.approx(expected_cf)

    def test_performance_ratio_iec_formula(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        final_yield = s.pv_production_mwh / inputs.pv.peak_power_mwp
        reference_yield = (s.pv_irradiation_wh_m2 / 1000.0) / 1.0
        assert s.pv_performance_ratio == pytest.approx(final_yield / reference_yield)

    def test_irradiation_is_poa_integral(self):
        bundle = _make_bundle()
        s = compute_plant_summary(bundle, SimulationInputs())
        expected = float(bundle["pv"]["poa"].sum() * INTERVAL_DURATION_H)
        assert s.pv_irradiation_wh_m2 == pytest.approx(expected)

    def test_production_is_ac_energy(self):
        bundle = _make_bundle()
        s = compute_plant_summary(bundle, SimulationInputs())
        expected = float(bundle["pv"]["p_ac_mw"].sum() * INTERVAL_DURATION_H)
        assert s.pv_production_mwh == pytest.approx(expected)

    def test_availability_only_counts_daylight(self):
        bundle = _make_bundle()
        s = compute_plant_summary(bundle, SimulationInputs())
        # Sin anomalías inyectadas, la planta produce siempre que hay sol.
        assert s.pv_availability == pytest.approx(100.0, abs=1.0)

    def test_pv_deviation_keys(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        devs = compute_pv_kpi_deviations(s, inputs)
        assert {
            "pv_capacity_factor", "pv_performance_ratio", "pv_availability",
            "pv_irradiation", "pv_production",
        } == set(devs)
        for v in devs.values():
            assert isinstance(v, float)

    def test_irradiation_deviation_vs_clearsky_non_positive(self):
        bundle = _make_bundle()
        inputs = SimulationInputs()
        s = compute_plant_summary(bundle, inputs)
        devs = compute_pv_kpi_deviations(s, inputs)
        # La irradiación real nunca supera el potencial de cielo claro.
        assert devs["pv_irradiation"] <= 0.0 + 1e-9

    def test_pv_kpis_empty_dataset_safe(self):
        s = compute_plant_summary(
            {"df": pd.DataFrame(), "pv": pd.DataFrame()}, SimulationInputs()
        )
        assert s.pv_capacity_factor == 0.0
        assert s.pv_production_mwh == 0.0
        devs = compute_pv_kpi_deviations(s, SimulationInputs())
        # Las referencias dinámicas (irradiación, producción) quedan a 0.
        assert devs["pv_irradiation"] == 0.0
        assert devs["pv_production"] == 0.0
        for v in devs.values():
            assert isinstance(v, float)

