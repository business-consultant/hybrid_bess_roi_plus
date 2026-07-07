from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS simulations (
    id                     TEXT PRIMARY KEY,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    name                   TEXT,
    seed                   INTEGER,
    -- Economic
    capex_per_mw           REAL NOT NULL,
    opex_per_mw_year       REAL NOT NULL,
    discount_rate          REAL NOT NULL,
    avg_spread_price       REAL NOT NULL,
    tax_rate               REAL NOT NULL,
    inflation_rate         REAL NOT NULL,
    -- BESS
    rated_power_mw         REAL NOT NULL,
    c_rate_inverse         REAL NOT NULL,
    nominal_power          REAL NOT NULL,
    eqo_cycles             REAL NOT NULL,
    lifespan_years         INTEGER NOT NULL,
    -- Efficiency
    initial_soh            REAL NOT NULL,
    rte                    REAL NOT NULL,
    degradation_per_cycle  REAL NOT NULL,
    soh_min                REAL NOT NULL,
    max_dod                REAL NOT NULL,
    min_soc                REAL NOT NULL,
    -- Activity
    year_cycles            REAL NOT NULL,
    -- Results
    roi                    REAL NOT NULL,
    van                    REAL NOT NULL,
    total_incumplimientos  INTEGER NOT NULL,
    yearly_summary_json    TEXT NOT NULL,
    parquet_path           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_runs (
    id                            TEXT PRIMARY KEY,
    created_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    name                          TEXT,
    asset                         TEXT,
    start_date                    TEXT NOT NULL,
    hoy                           TEXT NOT NULL,
    end_date                      TEXT NOT NULL,
    rated_power_mw                REAL NOT NULL,
    c_rate_inverse                REAL NOT NULL,
    avg_spread_eur                REAL NOT NULL,
    future_cycles_per_day         REAL NOT NULL,
    future_rte                    REAL NOT NULL,
    future_degradation_per_cycle  REAL NOT NULL,
    max_dod                       REAL NOT NULL,
    seed                          INTEGER,
    parquet_path                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sensitivity_results (
    id                TEXT PRIMARY KEY,
    simulation_id     TEXT NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    matrix_json       TEXT NOT NULL,
    capex_values_json TEXT NOT NULL,
    price_values_json TEXT NOT NULL
);
"""


def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_TABLES_SQL)

        row = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
        if row[0] is None:
            conn.execute(
                "INSERT INTO _schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()
    finally:
        conn.close()
