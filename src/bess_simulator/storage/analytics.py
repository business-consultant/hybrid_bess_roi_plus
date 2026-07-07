from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def compare_simulations(
    sim_ids: list[str],
    parquet_dir: Path,
) -> pd.DataFrame:
    queries = []
    for sim_id in sim_ids:
        path = (parquet_dir / f"sim_{sim_id}.parquet").as_posix()
        queries.append(
            f"SELECT '{sim_id}' AS simulation_id, * FROM read_parquet('{path}')"
        )
    sql = " UNION ALL ".join(queries)

    conn = duckdb.connect(":memory:")
    try:
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def query_interval_data(
    sim_id: str,
    sql: str,
    parquet_dir: Path,
) -> pd.DataFrame:
    path = (parquet_dir / f"sim_{sim_id}.parquet").as_posix()
    full_sql = sql.replace("{table}", f"read_parquet('{path}')")

    conn = duckdb.connect(":memory:")
    try:
        return conn.execute(full_sql).fetchdf()
    finally:
        conn.close()


def aggregate_dashboard_kpis(
    run_id: str,
    parquet_dir: Path,
) -> dict:
    path = (parquet_dir / f"dash_{run_id}.parquet").as_posix()
    sql = f"""
        SELECT
            SUM(income) AS total_income,
            AVG(capture_price) AS avg_capture_price,
            AVG(average_market_price) AS avg_market_price,
            SUM(energy_sold_mwh) AS total_energy_sold,
            MIN(soh) AS min_soh,
            AVG(rte) AS avg_rte,
            AVG(temperature) AS avg_temperature
        FROM read_parquet('{path}')
    """

    conn = duckdb.connect(":memory:")
    try:
        row = conn.execute(sql).fetchone()
        cols = [d[0] for d in conn.description]
        return dict(zip(cols, row))
    finally:
        conn.close()
