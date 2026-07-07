import pandas as pd
import numpy as np
import pytest

from bess_simulator.data.synthetic import generate_dashboard_dataset, aggregate_to_daily


@pytest.fixture
def dataset():
    return generate_dashboard_dataset(
        start_date="2024-06-01",
        hoy="2025-06-01",
        end_date="2026-06-01",
        seed=42,
    )


class TestDashboardDataset:
    def test_columns(self, dataset):
        expected = {
            "timestamp", "income", "capture_price", "average_market_price",
            "energy_sold_mwh", "soh", "cycles", "temperature", "rte", "is_forecast",
        }
        assert set(dataset.columns) == expected

    def test_soh_decreasing_daily(self, dataset):
        daily = aggregate_to_daily(dataset)
        soh_values = daily["soh"].values
        diffs = np.diff(soh_values)
        pct_decreasing = np.sum(diffs <= 0.001) / len(diffs)
        assert pct_decreasing > 0.90, f"SoH should be mostly decreasing, got {pct_decreasing:.0%}"

    def test_prices_in_omie_range(self, dataset):
        assert dataset["average_market_price"].min() >= 20.0
        assert dataset["average_market_price"].max() <= 200.0
        assert dataset["capture_price"].min() >= 20.0

    def test_soh_continuity_at_hoy(self, dataset):
        hoy = pd.Timestamp("2025-06-01")
        before = dataset[dataset["timestamp"] < hoy]["soh"].iloc[-1]
        after = dataset[dataset["timestamp"] >= hoy]["soh"].iloc[0]
        assert abs(before - after) < 0.005, f"SoH discontinuity: {before:.4f} -> {after:.4f}"

    def test_is_forecast_flag(self, dataset):
        hoy = pd.Timestamp("2025-06-01")
        hist = dataset[dataset["timestamp"] < hoy]
        fore = dataset[dataset["timestamp"] >= hoy]
        assert (hist["is_forecast"] == False).all()
        assert (fore["is_forecast"] == True).all()

    def test_aggregate_to_daily_preserves_forecast(self, dataset):
        daily = aggregate_to_daily(dataset)
        assert "is_forecast" in daily.columns
        assert daily["is_forecast"].dtype == bool or daily["is_forecast"].isin([True, False]).all()
        assert len(daily) > 0
