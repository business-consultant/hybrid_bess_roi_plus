from __future__ import annotations
import dataclasses
import pandas as pd
from bess_simulator.config import RANGES
from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import SensitivityResult
from bess_simulator.engine.simulation import run_simulation

# Desviaciones relativas respecto al caso base. El valor central (0.0) reproduce
# exactamente los inputs del usuario, de modo que la celda central de la matriz
# coincide con el ROI del caso base mostrado arriba.
PRICE_DEVIATIONS = [-0.30, -0.20, -0.10, 0.0, 0.10, 0.20, 0.30]   # ±30% del precio base
OPEX_DEVIATIONS = [-0.20, -0.10, 0.0, 0.10, 0.20]                # ±20% del OPEX base


def _opex_axis_values(base_opex: float) -> list[float]:
    """Valores de OPEX (€/MW·año) derivados de las desviaciones, recortados al
    rango permitido y sin duplicados, en orden creciente. El recorte evita que
    un OPEX base cercano al límite genere valores fuera de rango."""
    bounds = RANGES.get("opex_per_mw_year")
    values = []
    for d in OPEX_DEVIATIONS:
        v = round(base_opex * (1 + d))
        if bounds is not None:
            lo, hi = bounds
            v = min(max(v, lo), hi)
        values.append(v)
    return sorted(set(values))


def run_sensitivity_matrix(
    base_inputs: SimulationInputs,
    opex_values: list[float] | None = None,
    price_values: list[float] | None = None,
    seed: int | None = 42,
    advanced_config: dict | None = None,
) -> SensitivityResult:
    base_opex = base_inputs.economic.opex_per_mw_year
    base_price = base_inputs.economic.avg_spread_price
    if opex_values is None:
        opex_values = _opex_axis_values(base_opex)
    if price_values is None:
        price_values = [round(base_price * (1 + d), 2) for d in PRICE_DEVIATIONS]

    results = {}
    for price in price_values:
        row = {}
        for opex in opex_values:
            # Sobrescribimos solo OPEX y precio, preservando TODO lo demás del
            # caso base (modelo de ingresos, PV, red, eficiencia, etc.). Así la
            # celda (precio base, OPEX base) reproduce exactamente el ROI base.
            modified_economic = dataclasses.replace(
                base_inputs.economic, opex_per_mw_year=opex, avg_spread_price=price,
            )
            modified_inputs = dataclasses.replace(base_inputs, economic=modified_economic)
            sim_result = run_simulation(modified_inputs, seed=seed, advanced_config=advanced_config)
            row[opex] = sim_result.roi
        results[price] = row

    matrix = pd.DataFrame(results).T
    matrix.index.name = "price_eur_mwh"
    matrix.columns = [f"{int(c):,}" for c in opex_values]

    return SensitivityResult(matrix=matrix, opex_values=opex_values, price_values=price_values)
