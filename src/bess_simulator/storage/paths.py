from __future__ import annotations

import os
from pathlib import Path


def get_data_dir() -> Path:
    if os.environ.get("BESS_PORTABLE") == "1":
        base = Path(__file__).resolve().parents[3]
    else:
        base = Path(__file__).resolve().parents[4]

    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    return get_data_dir() / "bess.db"


def get_parquet_dir() -> Path:
    parquet_dir = get_data_dir() / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    return parquet_dir
