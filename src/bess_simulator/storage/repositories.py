from __future__ import annotations

import json
import sqlite3
import uuid
from io import StringIO
from pathlib import Path

import pandas as pd

from bess_simulator.models.parameters import (
    ActivityParams,
    BessParams,
    EconomicParams,
    EfficiencyParams,
    SimulationInputs,
)
from bess_simulator.models.results import SensitivityResult, SimulationResults


class SimulationRepository:

    def __init__(self, db_path: Path, parquet_dir: Path) -> None:
        self._db_path = db_path
        self._parquet_dir = parquet_dir

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save(
        self,
        inputs: SimulationInputs,
        results: SimulationResults,
        name: str | None = None,
        seed: int | None = None,
    ) -> str:
        sim_id = uuid.uuid4().hex
        parquet_name = f"sim_{sim_id}.parquet"
        parquet_path = self._parquet_dir / parquet_name
        results.interval_data.to_parquet(parquet_path, engine="pyarrow", compression="snappy")

        yearly_json = results.yearly_summary.to_json(orient="records", date_format="iso")

        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO simulations (
                    id, name, seed,
                    capex_per_mw, opex_per_mw_year, discount_rate, avg_spread_price,
                    tax_rate, inflation_rate,
                    rated_power_mw, c_rate_inverse, nominal_power, eqo_cycles, lifespan_years,
                    initial_soh, rte, degradation_per_cycle, soh_min, max_dod, min_soc,
                    year_cycles,
                    roi, van, total_incumplimientos,
                    yearly_summary_json, parquet_path
                ) VALUES (
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?
                )""",
                (
                    sim_id, name, seed,
                    inputs.economic.capex_per_mw, inputs.economic.opex_per_mw_year,
                    inputs.economic.discount_rate, inputs.economic.avg_spread_price,
                    inputs.economic.tax_rate, inputs.economic.inflation_rate,
                    inputs.bess.rated_power_mw, inputs.bess.c_rate_inverse,
                    inputs.bess.nominal_power, inputs.bess.eqo_cycles, inputs.bess.lifespan_years,
                    inputs.efficiency.initial_soh, inputs.efficiency.rte,
                    inputs.efficiency.degradation_per_cycle, inputs.efficiency.soh_min,
                    inputs.efficiency.max_dod, inputs.efficiency.min_soc,
                    inputs.activity.year_cycles,
                    results.roi, results.van, results.total_incumplimientos,
                    yearly_json, parquet_name,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return sim_id

    def list_all(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, created_at, roi, van, total_incumplimientos "
                "FROM simulations ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_metadata(self, sim_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def load_interval_data(self, sim_id: str) -> pd.DataFrame:
        meta = self.get_metadata(sim_id)
        if meta is None:
            raise KeyError(f"Simulación {sim_id} no encontrada")
        return pd.read_parquet(self._parquet_dir / meta["parquet_path"])

    def load_yearly_summary(self, sim_id: str) -> pd.DataFrame:
        meta = self.get_metadata(sim_id)
        if meta is None:
            raise KeyError(f"Simulación {sim_id} no encontrada")
        return pd.read_json(StringIO(meta["yearly_summary_json"]), orient="records")

    def load_inputs(self, sim_id: str) -> SimulationInputs:
        meta = self.get_metadata(sim_id)
        if meta is None:
            raise KeyError(f"Simulación {sim_id} no encontrada")
        return SimulationInputs(
            economic=EconomicParams(
                capex_per_mw=meta["capex_per_mw"],
                opex_per_mw_year=meta["opex_per_mw_year"],
                discount_rate=meta["discount_rate"],
                avg_spread_price=meta["avg_spread_price"],
                tax_rate=meta["tax_rate"],
                inflation_rate=meta["inflation_rate"],
            ),
            bess=BessParams(
                rated_power_mw=meta["rated_power_mw"],
                c_rate_inverse=meta["c_rate_inverse"],
                nominal_power=meta["nominal_power"],
                eqo_cycles=meta["eqo_cycles"],
                lifespan_years=int(meta["lifespan_years"]),
            ),
            efficiency=EfficiencyParams(
                initial_soh=meta["initial_soh"],
                rte=meta["rte"],
                degradation_per_cycle=meta["degradation_per_cycle"],
                soh_min=meta["soh_min"],
                max_dod=meta["max_dod"],
                min_soc=meta["min_soc"],
            ),
            activity=ActivityParams(year_cycles=meta["year_cycles"]),
        )

    def delete(self, sim_id: str) -> None:
        meta = self.get_metadata(sim_id)
        if meta is None:
            return
        parquet_file = self._parquet_dir / meta["parquet_path"]
        if parquet_file.exists():
            parquet_file.unlink()
        conn = self._connect()
        try:
            conn.execute("DELETE FROM simulations WHERE id = ?", (sim_id,))
            conn.commit()
        finally:
            conn.close()


class DashboardRepository:

    def __init__(self, db_path: Path, parquet_dir: Path) -> None:
        self._db_path = db_path
        self._parquet_dir = parquet_dir

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save(
        self,
        params: dict,
        df: pd.DataFrame,
        name: str | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        parquet_name = f"dash_{run_id}.parquet"
        parquet_path = self._parquet_dir / parquet_name
        df.to_parquet(parquet_path, engine="pyarrow", compression="snappy")

        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO dashboard_runs (
                    id, name, asset,
                    start_date, hoy, end_date,
                    rated_power_mw, c_rate_inverse,
                    avg_spread_eur, future_cycles_per_day, future_rte,
                    future_degradation_per_cycle, max_dod, seed,
                    parquet_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id, name, params.get("asset"),
                    params["start_date"], params["hoy"], params["end_date"],
                    params.get("rated_power_mw", 50),
                    params.get("c_rate_inverse", 4),
                    params["avg_spread_eur"], params["future_cycles_per_day"],
                    params["future_rte"], params["future_degradation_per_cycle"],
                    params["max_dod"], params.get("seed"),
                    parquet_name,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return run_id

    def list_all(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, asset, created_at, start_date, end_date "
                "FROM dashboard_runs ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def load_dataset(self, run_id: str) -> pd.DataFrame:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT parquet_path FROM dashboard_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Dashboard run {run_id} no encontrado")
            return pd.read_parquet(self._parquet_dir / row["parquet_path"])
        finally:
            conn.close()

    def delete(self, run_id: str) -> None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT parquet_path FROM dashboard_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return
            parquet_file = self._parquet_dir / row["parquet_path"]
            if parquet_file.exists():
                parquet_file.unlink()
            conn.execute("DELETE FROM dashboard_runs WHERE id = ?", (run_id,))
            conn.commit()
        finally:
            conn.close()


class SensitivityRepository:

    def __init__(self, db_path: Path, parquet_dir: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save(self, simulation_id: str, result: SensitivityResult) -> str:
        sens_id = uuid.uuid4().hex
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO sensitivity_results
                   (id, simulation_id, matrix_json, capex_values_json, price_values_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    sens_id,
                    simulation_id,
                    result.matrix.to_json(orient="split"),
                    json.dumps(result.opex_values),
                    json.dumps(result.price_values),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return sens_id

    def load(self, simulation_id: str) -> SensitivityResult | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM sensitivity_results WHERE simulation_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (simulation_id,),
            ).fetchone()
            if row is None:
                return None
            return SensitivityResult(
                matrix=pd.read_json(StringIO(row["matrix_json"]), orient="split"),
                opex_values=json.loads(row["capex_values_json"]),
                price_values=json.loads(row["price_values_json"]),
            )
        finally:
            conn.close()
