from __future__ import annotations
from pathlib import Path
import pandas as pd
from io import BytesIO

from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import SimulationResults


def export_simulation_to_excel(
    inputs: SimulationInputs,
    results: SimulationResults,
) -> bytes:
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        inputs_data = {
            "Parameter": [
                "CAPEX (€/MW)", "OPEX (€/MW/año)", "Discount Rate",
                "Avg Spread Price (€/MWh)", "Tax Rate", "Inflation Rate",
                "Rated Power (MW)", "1/C-Rate (MWh/MW)", "Nominal Power",
                "Lifespan Cycles", "Lifespan (years)",
                "Initial SoH", "RTE", "Degradation/cycle",
                "SoH min", "Max DoD", "Min SoC",
                "Year Cycles",
            ],
            "Value": [
                inputs.economic.capex_per_mw, inputs.economic.opex_per_mw_year,
                inputs.economic.discount_rate, inputs.economic.avg_spread_price,
                inputs.economic.tax_rate, inputs.economic.inflation_rate,
                inputs.bess.rated_power_mw, inputs.bess.c_rate_inverse,
                inputs.bess.nominal_power, inputs.bess.eqo_cycles,
                inputs.bess.lifespan_years,
                inputs.efficiency.initial_soh, inputs.efficiency.rte,
                inputs.efficiency.degradation_per_cycle, inputs.efficiency.soh_min,
                inputs.efficiency.max_dod, inputs.efficiency.min_soc,
                inputs.activity.year_cycles,
            ],
        }
        pd.DataFrame(inputs_data).to_excel(writer, sheet_name="Inputs", index=False)

        results.yearly_summary.to_excel(writer, sheet_name="Resumen Anual", index=False)

        outputs_data = {
            "Metric": ["ROI (%)", "VAN (€)", "Incumplimientos"],
            "Value": [f"{results.roi:.2%}", f"{results.van:,.2f}", results.total_incumplimientos],
        }
        pd.DataFrame(outputs_data).to_excel(writer, sheet_name="Outputs", index=False)

    return buffer.getvalue()


def export_historical_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def export_dataset_layers_to_excel(bundle: dict) -> bytes:
    """Exporta las tres capas del dataset activo a un Excel multihoja.

    Cada capa (BESS, meteorología, generación PV) se genera a resolución de
    15 minutos, por lo que se escribe tal cual en su propia hoja.
    """
    layers = [
        ("BESS", bundle.get("df")),
        ("Meteorologia", bundle.get("meteo")),
        ("Generacion PV", bundle.get("pv")),
    ]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, frame in layers:
            if frame is None:
                frame = pd.DataFrame()
            frame.to_excel(writer, sheet_name=sheet_name, index=False)

    return buffer.getvalue()


def export_dashboard_to_csv(
    df: pd.DataFrame,
    regime: str = "all",
) -> bytes:
    if regime == "historical":
        filtered = df[~df["is_forecast"]]
    elif regime == "forecast":
        filtered = df[df["is_forecast"]]
    else:
        filtered = df
    return filtered.to_csv(index=False).encode("utf-8")
