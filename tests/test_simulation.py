import pytest
import json
from pathlib import Path
from bess_simulator.models.parameters import (
    SimulationInputs, EconomicParams, BessParams, EfficiencyParams, ActivityParams
)
from bess_simulator.engine.simulation import run_simulation


@pytest.fixture
def default_inputs():
    return SimulationInputs()


@pytest.fixture
def reference_data():
    path = Path(__file__).parent / "test_data" / "excel_reference.json"
    with open(path) as f:
        return json.load(f)


class TestSimulationDeterministic:
    """Tests with seed=42 for reproducibility"""

    def test_roi_within_tolerance(self, default_inputs, reference_data):
        result = run_simulation(default_inputs, seed=42)
        expected = reference_data["expected_seed_42"]["roi"]
        assert abs(result.roi - expected) < 0.01  # 1% tolerance

    def test_van_positive(self, default_inputs):
        result = run_simulation(default_inputs, seed=42)
        assert result.van > 0

    def test_total_intervals(self, default_inputs):
        result = run_simulation(default_inputs, seed=42)
        assert len(result.interval_data) == 525_600  # 15 * 365 * 96

    def test_yearly_summary_rows(self, default_inputs):
        result = run_simulation(default_inputs, seed=42)
        assert len(result.yearly_summary) == 15

    def test_soh_decreasing(self, default_inputs):
        result = run_simulation(default_inputs, seed=42)
        soh_values = result.yearly_summary["soh_end"].values
        for i in range(1, len(soh_values)):
            assert soh_values[i] < soh_values[i - 1]

    def test_soh_compliance_transition(self, default_inputs):
        result = run_simulation(default_inputs, seed=42)
        ys = result.yearly_summary
        compliant = ys[ys["soh_compliance"] == True]
        non_compliant = ys[ys["soh_compliance"] == False]
        assert len(compliant) > 0
        assert len(non_compliant) > 0
        # Compliant years should come before non-compliant
        assert compliant["year"].max() < non_compliant["year"].min()

    def test_incumplimientos_count(self, default_inputs):
        result = run_simulation(default_inputs, seed=42)
        assert result.total_incumplimientos > 0

    def test_reproducibility(self, default_inputs):
        r1 = run_simulation(default_inputs, seed=42)
        r2 = run_simulation(default_inputs, seed=42)
        assert r1.roi == r2.roi
        assert r1.van == r2.van


class TestSimulationProperties:
    """Property-based tests"""

    def test_higher_capex_lower_roi(self):
        base = SimulationInputs()
        high_capex = SimulationInputs(economic=EconomicParams(capex_per_mw=900_000))
        r_base = run_simulation(base, seed=42)
        r_high = run_simulation(high_capex, seed=42)
        assert r_high.roi < r_base.roi

    def test_higher_price_higher_van(self):
        low = SimulationInputs(economic=EconomicParams(avg_spread_price=30))
        high = SimulationInputs(economic=EconomicParams(avg_spread_price=90))
        r_low = run_simulation(low, seed=42)
        r_high = run_simulation(high, seed=42)
        assert r_high.van > r_low.van

    def test_accumulated_dcf_starts_negative(self, default_inputs=SimulationInputs()):
        result = run_simulation(default_inputs, seed=42)
        first_dcf = result.interval_data["accumulated_dcf"].iloc[0]
        assert first_dcf < 0


class TestValidation:
    def test_capex_out_of_range(self):
        with pytest.raises(ValueError, match="capex_per_mw"):
            EconomicParams(capex_per_mw=100)

    def test_rte_out_of_range(self):
        with pytest.raises(ValueError, match="rte"):
            EfficiencyParams(rte=0.5)

    def test_valid_defaults(self):
        si = SimulationInputs()
        assert si.total_capex == 20_000_000
        assert si.total_capacity_mwh == 200
