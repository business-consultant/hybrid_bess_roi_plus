"""Tests de la Fase 5: streams de ingreso (a/b/c/d) y economía híbrida PV+BESS."""

import pytest

from bess_simulator.models.parameters import (
    SimulationInputs, RevenueParams, RevenueModel, GridParams, PvParams, HybridParams,
)
from bess_simulator.engine.simulation import run_simulation
from bess_simulator.engine.hybrid import compute_hybrid_economics
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG


class TestRevenueStreams:
    def test_model_a_only_arbitrage(self):
        inputs = SimulationInputs(revenue=RevenueParams(model=RevenueModel.ARBITRAGE))
        r = run_simulation(inputs, seed=42)
        b = r.revenue_breakdown
        assert b.arbitrage > 0
        assert b.ppa == 0
        assert b.capacity == 0
        assert b.secondary == 0

    def test_model_b_adds_ppa(self):
        inputs = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA, ppa_energy_share=0.5, ppa_price=60.0))
        r = run_simulation(inputs, seed=42)
        b = r.revenue_breakdown
        assert b.ppa > 0
        assert b.arbitrage > 0
        assert b.capacity == 0

    def test_model_c_adds_capacity(self):
        inputs = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA_CAPACITY,
            capacity_price_eur_mw_year=25_000, committed_mw=40))
        r = run_simulation(inputs, seed=42)
        assert r.revenue_breakdown.capacity > 0

    def test_model_d_adds_secondary(self):
        inputs = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
            secondary_band_up_mw=10, secondary_band_down_mw=10, secondary_price=25))
        r = run_simulation(inputs, seed=42)
        assert r.revenue_breakdown.secondary > 0

    def test_capacity_payment_value(self):
        # Capacidad: ingreso anual fijo = precio × MW comprometidos × años.
        inputs = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA_CAPACITY,
            capacity_price_eur_mw_year=20_000, committed_mw=10))
        r = run_simulation(inputs, seed=42)
        expected = 20_000 * 10 * inputs.bess.lifespan_years
        assert r.revenue_breakdown.capacity == pytest.approx(expected, rel=0.01)

    def test_asymmetric_secondary_band(self):
        # Banda asimétrica: subir ≠ bajar debe dar más ingreso que solo una de ellas.
        sym = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
            secondary_band_up_mw=10, secondary_band_down_mw=10, secondary_price=25))
        asym = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
            secondary_band_up_mw=20, secondary_band_down_mw=5, secondary_price=25))
        r_sym = run_simulation(sym, seed=42)
        r_asym = run_simulation(asym, seed=42)
        # Banda total: sym=20, asym=25 → asym mayor disponibilidad.
        assert r_asym.revenue_breakdown.secondary > r_sym.revenue_breakdown.secondary

    def test_breakdown_total_matches_income(self):
        inputs = SimulationInputs(revenue=RevenueParams(
            model=RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
            ppa_energy_share=0.4))
        r = run_simulation(inputs, seed=42)
        income_sum = float(r.interval_data["income"].sum())
        assert r.revenue_breakdown.total == pytest.approx(income_sum, rel=1e-6)


class TestHybridEconomics:
    def test_returns_economics(self):
        inputs = SimulationInputs()
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_annual_energy_mwh > 0
        assert h.pv_to_grid_mwh > 0

    def test_pv_roi_independent_of_bess(self):
        # El ROI PV no debe cambiar al cambiar el CAPEX de la BESS.
        a = SimulationInputs()
        b = SimulationInputs()
        b.economic.capex_per_mw = 800_000
        ha = compute_hybrid_economics(a, DEFAULT_ADVANCED_CONFIG, seed=42)
        hb = compute_hybrid_economics(b, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert ha.pv_roi == pytest.approx(hb.pv_roi, rel=1e-9)

    def test_curtailment_when_poi_tight(self):
        # POI muy por debajo de la potencia AC PV → curtailment > 0.
        inputs = SimulationInputs(
            pv=PvParams(peak_power_mwp=100, inverter_ac_mw=80),
            grid=GridParams(poi_limit_mw=10),
            hybrid=HybridParams(charge_priority="grid"),  # sin captura a BESS
        )
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_curtailed_mwh > 0

    def test_bess_captures_excess_over_poi(self):
        # Con prioridad pv_first, parte del excedente sobre POI va a la BESS.
        inputs = SimulationInputs(
            pv=PvParams(peak_power_mwp=100, inverter_ac_mw=80),
            grid=GridParams(poi_limit_mw=10),
            hybrid=HybridParams(charge_priority="pv_first"),
        )
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_to_bess_mwh > 0

    def test_no_capture_with_grid_priority(self):
        inputs = SimulationInputs(
            pv=PvParams(peak_power_mwp=100, inverter_ac_mw=80),
            grid=GridParams(poi_limit_mw=10),
            hybrid=HybridParams(charge_priority="grid"),
        )
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_to_bess_mwh == 0

    def test_pv_to_bess_share_without_poi_excess(self):
        # Sin excedente sobre el POI (POI ≥ inversor), la fracción pv_to_bess_share
        # garantiza flujo PV→BESS no nulo (corrige la inconsistencia previa).
        inputs = SimulationInputs(
            pv=PvParams(peak_power_mwp=60, inverter_ac_mw=48),
            grid=GridParams(poi_limit_mw=50),
            hybrid=HybridParams(charge_priority="pv_first", pv_to_bess_share=0.20),
        )
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_to_bess_mwh > 0

    def test_pv_to_bess_share_zero_no_diversion(self):
        # Con share=0 y sin excedente sobre el POI, no hay flujo PV→BESS.
        inputs = SimulationInputs(
            pv=PvParams(peak_power_mwp=60, inverter_ac_mw=48),
            grid=GridParams(poi_limit_mw=50),
            hybrid=HybridParams(charge_priority="pv_first", pv_to_bess_share=0.0),
        )
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_to_bess_mwh == 0

    def test_pv_to_bess_share_reduces_direct_injection(self):
        # La energía desviada a la BESS deja de inyectarse directa a red:
        # más share → menos pv_to_grid, conservando la energía total.
        base = SimulationInputs(
            pv=PvParams(peak_power_mwp=60, inverter_ac_mw=48),
            grid=GridParams(poi_limit_mw=50),
            hybrid=HybridParams(charge_priority="pv_first", pv_to_bess_share=0.0),
        )
        diverted = SimulationInputs(
            pv=PvParams(peak_power_mwp=60, inverter_ac_mw=48),
            grid=GridParams(poi_limit_mw=50),
            hybrid=HybridParams(charge_priority="pv_first", pv_to_bess_share=0.30),
        )
        hb = compute_hybrid_economics(base, DEFAULT_ADVANCED_CONFIG, seed=42)
        hd = compute_hybrid_economics(diverted, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert hd.pv_to_grid_mwh < hb.pv_to_grid_mwh
        # Lo que sale de inyección directa entra como carga de BESS (conservación).
        assert hd.pv_to_bess_mwh == pytest.approx(
            hb.pv_to_grid_mwh - hd.pv_to_grid_mwh, rel=1e-6
        )

    def test_clipping_with_high_ilr(self):
        # ILR alto (campo muy sobredimensionado) → clipping del inversor > 0.
        inputs = SimulationInputs(pv=PvParams(peak_power_mwp=100, inverter_ac_mw=40))
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_clipped_mwh > 0

    def test_poi_utilization_reported(self):
        inputs = SimulationInputs()
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.poi_utilization_peak == pytest.approx(inputs.poi_utilization_peak)


class TestHybridReconciliation:
    """Reconciliación PV↔BESS: coste cero de carga, crédito de sinergia, curtailment."""

    def test_concurrency_curtailment_reduces_net_injection(self):
        # El curtailment por concurrencia reduce la inyección neta vendible.
        inputs = SimulationInputs()
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        pct = DEFAULT_ADVANCED_CONFIG["poi_concurrency_curtail_pct"]
        assert pct > 0
        assert h.pv_curtailed_concurrency_mwh == pytest.approx(h.pv_to_grid_mwh * pct, rel=1e-9)
        assert h.pv_to_grid_net_mwh == pytest.approx(h.pv_to_grid_mwh - h.pv_curtailed_concurrency_mwh, rel=1e-9)
        assert h.pv_to_grid_net_mwh < h.pv_to_grid_mwh

    def test_curtailment_not_zero(self):
        # No se asume curtailment cero aunque el inversor esté por debajo del POI.
        inputs = SimulationInputs(pv=PvParams(peak_power_mwp=60, inverter_ac_mw=48),
                                  grid=GridParams(poi_limit_mw=50))
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.pv_curtailment_total_mwh > 0
        assert h.pv_curtailment_cost_total > 0

    def test_solar_fraction_in_range(self):
        inputs = SimulationInputs()
        r = run_simulation(inputs, seed=42)
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42, results=r)
        assert 0.0 < h.bess_solar_fraction <= 1.0
        assert h.bess_charge_demand_mwh > 0
        assert h.bess_solar_charge_mwh <= h.bess_charge_demand_mwh + 1e-6

    def test_synergy_credit_positive_with_solar_charge(self):
        # Con carga solar > 0 y precio de carga > 0, el crédito de sinergia es positivo.
        inputs = SimulationInputs()
        r = run_simulation(inputs, seed=42)
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42, results=r)
        assert h.synergy_pv_charge_credit > 0
        # El spread efectivo supera al base por la carga solar gratuita.
        assert h.bess_effective_spread > h.bess_base_spread

    def test_no_synergy_without_pv_charge(self):
        # Sin prioridad de carga PV (grid) no hay PV→BESS ni crédito.
        inputs = SimulationInputs(hybrid=HybridParams(charge_priority="grid_first"))
        r = run_simulation(inputs, seed=42)
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42, results=r)
        assert h.bess_solar_charge_mwh == 0.0
        assert h.synergy_pv_charge_credit == 0.0
        assert h.bess_effective_spread == pytest.approx(h.bess_base_spread)

    def test_analytic_fallback_without_results(self):
        # Sin pasar results, la demanda de carga se estima analíticamente (>0).
        inputs = SimulationInputs()
        h = compute_hybrid_economics(inputs, DEFAULT_ADVANCED_CONFIG, seed=42)
        assert h.bess_charge_demand_mwh > 0
        assert h.bess_solar_fraction > 0

