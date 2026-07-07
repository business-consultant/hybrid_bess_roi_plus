import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import SimulationResults, SensitivityResult
from bess_simulator.storage.schema import init_db
from bess_simulator.storage.repositories import (
    SimulationRepository,
    DashboardRepository,
    SensitivityRepository,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def parquet_dir(tmp_path):
    d = tmp_path / "parquet"
    d.mkdir()
    return d


@pytest.fixture
def sim_repo(db_path, parquet_dir):
    return SimulationRepository(db_path, parquet_dir)


@pytest.fixture
def dash_repo(db_path, parquet_dir):
    return DashboardRepository(db_path, parquet_dir)


@pytest.fixture
def sens_repo(db_path, parquet_dir):
    return SensitivityRepository(db_path, parquet_dir)


@pytest.fixture
def sample_inputs():
    return SimulationInputs()


@pytest.fixture
def sample_results():
    n_intervals = 96 * 10
    interval_data = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n_intervals, freq="15min"),
        "available_capacity": np.random.uniform(180, 200, n_intervals),
        "period_degradation": np.linspace(0, 0.05, n_intervals),
        "cycle_number": np.random.uniform(0, 0.02, n_intervals),
        "rte": np.random.uniform(0.82, 0.86, n_intervals),
        "sold_energy": np.random.uniform(0, 12, n_intervals),
        "spread_price": np.random.uniform(40, 90, n_intervals),
        "income": np.random.uniform(0, 500, n_intervals),
        "interval_opex": np.full(n_intervals, 1.5),
        "cash_flow": np.random.uniform(-2, 500, n_intervals),
        "discounted_cf": np.random.uniform(-2, 480, n_intervals),
        "accumulated_dcf": np.cumsum(np.random.uniform(-2, 480, n_intervals)),
    })
    yearly_summary = pd.DataFrame({
        "year": range(1, 4),
        "total_income": [1_000_000, 950_000, 900_000],
        "total_opex": [550_000, 550_000, 550_000],
        "net_cash_flow": [450_000, 400_000, 350_000],
        "accumulated_dcf": [450_000, 820_000, 1_130_000],
        "avg_degradation": [0.01, 0.02, 0.03],
        "avg_rte": [0.85, 0.84, 0.83],
        "soh_compliance": [True, True, True],
    })
    return SimulationResults(
        roi=0.15, van=2_500_000, interval_data=interval_data,
        yearly_summary=yearly_summary, total_incumplimientos=0,
    )


class TestInitDb:
    def test_creates_tables(self, db_path):
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        table_names = {t[0] for t in tables}
        assert "simulations" in table_names
        assert "dashboard_runs" in table_names
        assert "sensitivity_results" in table_names
        assert "_schema_version" in table_names

    def test_idempotent(self, db_path):
        init_db(db_path)
        init_db(db_path)


class TestSimulationRepository:
    def test_save_and_list(self, sim_repo, sample_inputs, sample_results):
        sim_id = sim_repo.save(sample_inputs, sample_results, name="Test sim", seed=42)
        assert isinstance(sim_id, str)
        assert len(sim_id) == 32

        sims = sim_repo.list_all()
        assert len(sims) == 1
        assert sims[0]["name"] == "Test sim"
        assert sims[0]["id"] == sim_id

    def test_load_interval_data(self, sim_repo, sample_inputs, sample_results):
        sim_id = sim_repo.save(sample_inputs, sample_results)
        loaded = sim_repo.load_interval_data(sim_id)
        pd.testing.assert_frame_equal(
            loaded.reset_index(drop=True),
            sample_results.interval_data.reset_index(drop=True),
        )

    def test_load_yearly_summary(self, sim_repo, sample_inputs, sample_results):
        sim_id = sim_repo.save(sample_inputs, sample_results)
        loaded = sim_repo.load_yearly_summary(sim_id)
        assert len(loaded) == len(sample_results.yearly_summary)
        assert list(loaded.columns) == list(sample_results.yearly_summary.columns)

    def test_load_inputs_roundtrip(self, sim_repo, sample_inputs, sample_results):
        sim_id = sim_repo.save(sample_inputs, sample_results)
        loaded = sim_repo.load_inputs(sim_id)
        assert loaded.economic.capex_per_mw == sample_inputs.economic.capex_per_mw
        assert loaded.bess.rated_power_mw == sample_inputs.bess.rated_power_mw
        assert loaded.efficiency.rte == sample_inputs.efficiency.rte
        assert loaded.activity.year_cycles == sample_inputs.activity.year_cycles

    def test_get_metadata(self, sim_repo, sample_inputs, sample_results):
        sim_id = sim_repo.save(sample_inputs, sample_results, name="meta test")
        meta = sim_repo.get_metadata(sim_id)
        assert meta is not None
        assert meta["roi"] == pytest.approx(0.15)
        assert meta["van"] == pytest.approx(2_500_000)
        assert meta["name"] == "meta test"

    def test_delete(self, sim_repo, sample_inputs, sample_results, parquet_dir):
        sim_id = sim_repo.save(sample_inputs, sample_results)
        assert len(sim_repo.list_all()) == 1
        assert (parquet_dir / f"sim_{sim_id}.parquet").exists()

        sim_repo.delete(sim_id)
        assert len(sim_repo.list_all()) == 0
        assert not (parquet_dir / f"sim_{sim_id}.parquet").exists()

    def test_not_found_raises(self, sim_repo):
        with pytest.raises(KeyError):
            sim_repo.load_interval_data("nonexistent")


class TestDashboardRepository:
    def test_save_and_load(self, dash_repo):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=96, freq="15min"),
            "income": np.random.uniform(0, 100, 96),
            "capture_price": np.random.uniform(40, 80, 96),
            "average_market_price": np.random.uniform(40, 80, 96),
            "energy_sold_mwh": np.random.uniform(0, 12, 96),
            "soh": np.linspace(1.0, 0.99, 96),
            "cycles": np.random.uniform(0, 0.02, 96),
            "temperature": np.random.uniform(20, 35, 96),
            "rte": np.random.uniform(0.82, 0.88, 96),
            "is_forecast": [False] * 96,
        })
        params = {
            "asset": "PV Jarama n4",
            "start_date": "2024-06-01", "hoy": "2024-12-01", "end_date": "2025-06-01",
            "avg_spread_eur": 40.0, "future_cycles_per_day": 1.5,
            "future_rte": 0.84, "future_degradation_per_cycle": 0.0001,
            "max_dod": 0.90, "seed": 42,
        }
        run_id = dash_repo.save(params, df, name="Test dash")
        runs = dash_repo.list_all()
        assert len(runs) == 1
        assert runs[0]["name"] == "Test dash"

        loaded = dash_repo.load_dataset(run_id)
        assert len(loaded) == 96

    def test_delete(self, dash_repo, parquet_dir):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=10, freq="15min"),
            "income": np.zeros(10),
            "capture_price": np.zeros(10),
            "average_market_price": np.zeros(10),
            "energy_sold_mwh": np.zeros(10),
            "soh": np.ones(10),
            "cycles": np.zeros(10),
            "temperature": np.full(10, 25.0),
            "rte": np.full(10, 0.84),
            "is_forecast": [False] * 10,
        })
        params = {
            "asset": "test", "start_date": "2024-06-01", "hoy": "2024-12-01",
            "end_date": "2025-06-01", "avg_spread_eur": 40.0,
            "future_cycles_per_day": 1.5, "future_rte": 0.84,
            "future_degradation_per_cycle": 0.0001, "max_dod": 0.90,
        }
        run_id = dash_repo.save(params, df)
        dash_repo.delete(run_id)
        assert len(dash_repo.list_all()) == 0


class TestSensitivityRepository:
    def test_save_and_load(self, sens_repo, sim_repo, sample_inputs, sample_results):
        sim_id = sim_repo.save(sample_inputs, sample_results)
        matrix = pd.DataFrame(
            np.random.uniform(0, 0.3, (5, 5)),
            columns=[8_800, 9_900, 11_000, 12_100, 13_200],
        )
        result = SensitivityResult(
            matrix=matrix,
            opex_values=[8_800, 9_900, 11_000, 12_100, 13_200],
            price_values=[30, 40, 50, 60, 70],
        )
        sens_repo.save(sim_id, result)
        loaded = sens_repo.load(sim_id)
        assert loaded is not None
        assert loaded.matrix.shape == (5, 5)
        assert loaded.opex_values == result.opex_values
        assert loaded.price_values == result.price_values

    def test_load_nonexistent(self, sens_repo):
        assert sens_repo.load("nonexistent") is None
