from __future__ import annotations

import numpy as np
import pandas as pd

from bess_simulator.config import INTERVALS_PER_DAY, INTERVAL_DURATION_H
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG
from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import SimulationResults, RevenueBreakdown

_START_DATE = pd.Timestamp("2025-01-01")


def run_simulation(
    inputs: SimulationInputs,
    seed: int | None = None,
    advanced_config: dict | None = None,
) -> SimulationResults:
    cfg = advanced_config or DEFAULT_ADVANCED_CONFIG
    total_days = inputs.bess.lifespan_years * 365
    total_intervals = total_days * INTERVALS_PER_DAY
    capacity_0 = inputs.total_capacity_mwh * inputs.efficiency.initial_soh
    rng = np.random.default_rng(seed)

    slot_cycles_base = inputs.daily_cycles / INTERVALS_PER_DAY
    rte_base = inputs.efficiency.rte
    avg_price = inputs.economic.avg_spread_price

    cycle_var = cfg["sim_cycle_variation"]
    slot_cycles = slot_cycles_base + rng.uniform(0.0, cycle_var * slot_cycles_base, total_intervals)

    day_indices = np.repeat(np.arange(total_days), INTERVALS_PER_DAY)
    rte_trend = rte_base - cfg["rte_annual_decay"] * (day_indices / 365.0)
    slot_rte = np.clip(
        rte_trend + rng.normal(0, cfg["sim_rte_noise_std"], total_intervals),
        cfg["rte_floor"], cfg["rte_ceiling"],
    )

    price_floor = avg_price * cfg["sim_price_floor_factor"]
    slot_prices = price_floor + rng.uniform(0.0, cfg["sim_price_range_factor"] * price_floor, total_intervals)

    slot_cycles_2d = slot_cycles.reshape(total_days, INTERVALS_PER_DAY)

    daily_cycles = slot_cycles_2d.sum(axis=1)

    cumulative_days = np.arange(1, total_days + 1, dtype=float)
    calendar_loss = cfg["calendar_aging_rate"] * (cumulative_days / 365.0)
    cycle_loss = np.cumsum(inputs.efficiency.degradation_per_cycle * daily_cycles)
    daily_degradation = calendar_loss + cycle_loss

    daily_available_capacity = (1.0 - daily_degradation) * capacity_0

    slot_avail_cap = np.repeat(daily_available_capacity, INTERVALS_PER_DAY)
    slot_degradation = np.repeat(daily_degradation, INTERVALS_PER_DAY)

    # FIX-2: Energía = Capacidad × fracción_ciclo × RTE × DOD (sin × 0.25h extra)
    slot_sold_energy = (
        slot_avail_cap
        * slot_cycles
        * slot_rte
        * inputs.efficiency.max_dod
    )

    # --- Streams de ingreso según el modelo de negocio (a/b/c/d) ---
    revenue = inputs.revenue
    model = revenue.model

    # a) Arbitraje + b) PPA: una fracción de la energía se vende a precio PPA fijo.
    ppa_share = revenue.ppa_energy_share if model.has_ppa else 0.0
    energy_market = slot_sold_energy * (1.0 - ppa_share)
    energy_ppa = slot_sold_energy * ppa_share
    slot_income_arbitrage = energy_market * slot_prices
    slot_income_ppa = energy_ppa * revenue.ppa_price

    # c) Pago por capacidad: ingreso anual fijo por potencia firme comprometida.
    if model.has_capacity:
        capacity_per_interval = (
            revenue.capacity_price_eur_mw_year * revenue.committed_mw
        ) / (365 * INTERVALS_PER_DAY)
    else:
        capacity_per_interval = 0.0
    slot_income_capacity = np.full(total_intervals, capacity_per_interval)

    # d) Regulación secundaria: disponibilidad de banda (subir+bajar) + activación.
    if model.has_secondary:
        band_total = revenue.secondary_band_total_mw
        availability = revenue.secondary_price * band_total * INTERVAL_DURATION_H
        activation_energy = band_total * revenue.secondary_activation_rate * INTERVAL_DURATION_H
        slot_income_secondary = availability + activation_energy * slot_prices
    else:
        slot_income_secondary = np.zeros(total_intervals)

    slot_income = (
        slot_income_arbitrage
        + slot_income_ppa
        + slot_income_capacity
        + slot_income_secondary
    )
    interval_opex = inputs.daily_opex / INTERVALS_PER_DAY
    slot_cash_flow = slot_income - interval_opex

    interval_indices = np.arange(1, total_intervals + 1)
    day_fraction = interval_indices / INTERVALS_PER_DAY / 365.0
    discount_factors = (1.0 + inputs.economic.discount_rate) ** day_fraction
    slot_discounted_cf = slot_cash_flow / discount_factors

    slot_accumulated_dcf = np.empty(total_intervals + 1)
    slot_accumulated_dcf[0] = -inputs.total_capex
    slot_accumulated_dcf[1:] = -inputs.total_capex + np.cumsum(slot_discounted_cf)

    # FIX-3: VAN incluye -CAPEX (antes solo sumaba DCF sin inversión inicial)
    van = float(slot_accumulated_dcf[-1])

    # FIX-4: ROI anualizado para ser comparable con tasa de descuento
    roi_total = slot_accumulated_dcf[-1] / inputs.total_capex
    roi = float((1.0 + roi_total) ** (1.0 / inputs.bess.lifespan_years) - 1.0)

    total_incumplimientos = int(np.sum(slot_degradation > (1.0 - inputs.efficiency.soh_min)))

    timestamps = pd.date_range(
        start=_START_DATE,
        periods=total_intervals,
        freq="15min",
    )

    interval_data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "available_capacity": slot_avail_cap,
            "period_degradation": slot_degradation,
            "cycle_number": slot_cycles,
            "rte": slot_rte,
            "sold_energy": slot_sold_energy,
            "spread_price": slot_prices,
            "income": slot_income,
            "interval_opex": interval_opex,
            "cash_flow": slot_cash_flow,
            "discounted_cf": slot_discounted_cf,
            "accumulated_dcf": slot_accumulated_dcf[1:],
        }
    )

    interval_data["year"] = (
        (interval_data.index // INTERVALS_PER_DAY) // 365
    ).astype(int)

    daily_cycles_series = np.repeat(daily_cycles, INTERVALS_PER_DAY)
    interval_data["_daily_cycles_rep"] = daily_cycles_series

    yearly_summary = (
        interval_data.groupby("year")
        .agg(
            total_income=("income", "sum"),
            total_opex=("interval_opex", "sum"),
            net_cash_flow=("cash_flow", "sum"),
            accumulated_dcf=("accumulated_dcf", "last"),
            avg_degradation=("period_degradation", "mean"),
            avg_rte=("rte", "mean"),
            soh_compliance=("period_degradation", lambda x: bool((x <= (1.0 - inputs.efficiency.soh_min)).all())),
        )
        .reset_index()
    )
    yearly_summary["soh_end"] = 1.0 - (
        interval_data.groupby("year")["period_degradation"].max().values
    )

    interval_data = interval_data.drop(columns=["year", "_daily_cycles_rep"])

    revenue_breakdown = RevenueBreakdown(
        arbitrage=float(slot_income_arbitrage.sum()),
        ppa=float(slot_income_ppa.sum()),
        capacity=float(slot_income_capacity.sum()),
        secondary=float(slot_income_secondary.sum()),
    )

    return SimulationResults(
        roi=roi,
        van=van,
        interval_data=interval_data,
        yearly_summary=yearly_summary,
        total_incumplimientos=total_incumplimientos,
        revenue_breakdown=revenue_breakdown,
    )
