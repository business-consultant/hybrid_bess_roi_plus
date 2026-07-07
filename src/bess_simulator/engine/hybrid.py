"""Motor de despacho híbrido PV+BESS y economía independiente de la PV (Fase 5).

Calcula, sobre un año representativo a resolución de 15 minutos:
  - La generación PV con el dimensionado real del operador (PvParams).
  - Los flujos en el punto de interconexión (POI): cuánta energía PV se inyecta
    directamente a red, cuánta se desvía a la BESS (captura del excedente sobre
    el POI más la fracción ``pv_to_bess_share`` enrutada intencionadamente a la
    batería para exportarla más tarde) y cuánta se recorta (curtailment),
    además del recorte DC del inversor (clipping por ILR).
  - La economía de la PV (ROI y VAN) de forma INDEPENDIENTE de la BESS: la PV
    tiene su propio CAPEX/OPEX y no comparte inversión con la batería.

Simplificaciones de prototipo (documentadas):
  - El precio de venta de la energía PV usa ``avg_spread_price`` como proxy del
    precio de pool; la fracción bajo PPA se remunera a ``ppa_price``.
  - La energía PV desviada a la BESS se asigna a COSTE DE CARGA CERO: la PV no
    cobra por ella (no se cuenta como ingreso PV, evitando doble contabilidad) y
    la BESS la recibe gratis. El ahorro frente a comprar esa carga en el pool
    (``bess_grid_charge_price``) se reconoce como CRÉDITO DE SINERGIA y vitamina
    el spread efectivo de la batería. Reconciliación a nivel ANUAL agregado.
  - El curtailment NO se asume cero: además del recorte físico sobre el POI, se
    estima un residual por concurrencia PV+BESS en el POI compartido
    (``poi_concurrency_curtail_pct``) que reduce la producción PV vendible.
  - El año representativo se proyecta a la vida útil aplicando la degradación
    anual de la PV (lineal).

Detalle de la reconciliación PV↔BESS y de la estimación de curtailment en
``docs/02-design/balance-hibrido-pv-bess.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bess_simulator.config import INTERVAL_DURATION_H
from bess_simulator.data.meteo import generate_meteo_dataset
from bess_simulator.data.pv import generate_pv_dataset
from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import HybridEconomics, SimulationResults

_REPRESENTATIVE_START = "2025-01-01"
_REPRESENTATIVE_END = "2026-01-01"


def _representative_pv_frame(inputs: SimulationInputs, cfg: dict, seed: int | None) -> pd.DataFrame:
    """Genera la PV de un año representativo con el dimensionado del operador."""
    meteo_df = generate_meteo_dataset(
        start_date=_REPRESENTATIVE_START,
        end_date=_REPRESENTATIVE_END,
        latitude=inputs.pv.latitude,
        cfg=cfg,
        seed=seed,
    )
    return generate_pv_dataset(meteo_df, inputs.pv, cfg)


def _bess_annual_discharge_mwh(
    inputs: SimulationInputs, results: SimulationResults | None
) -> float:
    """Energía anual descargada por la BESS en el año 1 (MWh).

    Si se dispone de los resultados del Simulador ROI se toma directamente la
    energía vendida del año 1 (coherencia exacta con la pantalla del simulador).
    En su defecto se estima de forma analítica: capacidad × ciclos × RTE × DoD.
    """
    if results is not None and results.interval_data is not None and not results.interval_data.empty:
        df = results.interval_data
        if "year" in df.columns and "sold_energy" in df.columns:
            year1 = df.loc[df["year"] == 0, "sold_energy"].sum()
            if year1 > 0:
                return float(year1)
    capacity0 = inputs.total_capacity_mwh * inputs.efficiency.initial_soh
    return float(
        capacity0
        * inputs.activity.year_cycles
        * inputs.efficiency.rte
        * inputs.efficiency.max_dod
    )


def compute_hybrid_economics(
    inputs: SimulationInputs,
    cfg: dict,
    seed: int | None = None,
    results: SimulationResults | None = None,
) -> HybridEconomics:
    """Calcula la economía PV y los flujos híbridos en el POI."""
    pv_df = _representative_pv_frame(inputs, cfg, seed)

    if pv_df.empty:
        return HybridEconomics(poi_utilization_peak=inputs.poi_utilization_peak)

    p_ac = pv_df["p_ac_mw"].to_numpy()
    p_clipped = pv_df["p_clipped_mw"].to_numpy()

    poi_limit = inputs.grid.poi_limit_mw
    bess_power = inputs.output_power_mw

    # Flujo en el POI (potencia instantánea, MW).
    pv_inject = np.minimum(p_ac, poi_limit)          # PV que cabe en el POI
    pv_over_poi = np.maximum(p_ac - poi_limit, 0.0)  # excedente sobre el POI

    pv_charges = inputs.hybrid.charge_priority in ("pv_first", "mixed")

    # 1) El excedente sobre el POI puede cargar la BESS (hasta su potencia
    #    nominal) si la estrategia lo permite; el resto se recorta (curtailment).
    if pv_charges:
        capture_over_poi = np.minimum(pv_over_poi, bess_power)
    else:
        capture_over_poi = np.zeros_like(pv_over_poi)
    pv_curtailed = pv_over_poi - capture_over_poi

    # 2) Derivación intencionada: una fracción de la PV que iría directa a red se
    #    enruta a la BESS para almacenarla y exportarla más tarde. Esto hace que
    #    el flujo PV→BESS sea no nulo aunque no haya excedente sobre el POI
    #    (coherente con "la BESS se alimenta de PV en primer lugar"). Limitado
    #    por la potencia disponible de la BESS tras capturar el excedente.
    share = inputs.hybrid.pv_to_bess_share if pv_charges else 0.0
    headroom = np.maximum(bess_power - capture_over_poi, 0.0)
    intentional_to_bess = np.minimum(pv_inject * share, headroom)

    pv_to_bess = capture_over_poi + intentional_to_bess
    pv_to_grid = pv_inject - intentional_to_bess  # lo que queda va directo a red

    # Energías anuales (MWh) = potencia (MW) × duración del intervalo (h).
    pv_to_grid_mwh = float(pv_to_grid.sum() * INTERVAL_DURATION_H)
    pv_to_bess_mwh = float(pv_to_bess.sum() * INTERVAL_DURATION_H)
    pv_curtailed_mwh = float(pv_curtailed.sum() * INTERVAL_DURATION_H)
    pv_clipped_mwh = float(p_clipped.sum() * INTERVAL_DURATION_H)
    pv_annual_energy_mwh = float(p_ac.sum() * INTERVAL_DURATION_H)

    # 3) Curtailment por CONCURRENCIA en el POI compartido. La PV y la descarga
    #    de la BESS comparten el mismo límite del POI; aunque un despacho
    #    inteligente evita la mayor parte del solapamiento, queda un residual
    #    (más órdenes de red) que se estima como un porcentaje de la inyección
    #    directa a red. No se asume curtailment cero. La energía recortada deja
    #    de ser vendible por la PV (se ajusta la producción final).
    concurrency_pct = float(cfg.get("poi_concurrency_curtail_pct", 0.03) or 0.0)
    concurrency_pct = min(max(concurrency_pct, 0.0), 1.0)
    pv_curtailed_concurrency_mwh = pv_to_grid_mwh * concurrency_pct
    pv_to_grid_net_mwh = pv_to_grid_mwh - pv_curtailed_concurrency_mwh
    pv_curtailment_total_mwh = pv_curtailed_mwh + pv_curtailed_concurrency_mwh

    # --- Economía PV independiente (vida útil) ---
    lifespan = inputs.bess.lifespan_years
    discount = inputs.economic.discount_rate
    annual_degr = inputs.pv.annual_degradation

    # Precio medio de venta PV (proxy de pool; fracción PPA a precio fijo).
    if inputs.revenue.model.has_ppa:
        share = inputs.revenue.ppa_energy_share
        pv_price = share * inputs.revenue.ppa_price + (1.0 - share) * inputs.economic.avg_spread_price
    else:
        pv_price = inputs.economic.avg_spread_price

    years = np.arange(1, lifespan + 1)
    degradation_factor = np.clip(1.0 - annual_degr * (years - 1), 0.0, 1.0)
    # Solo inyección directa NETA (tras curtailment de concurrencia). La energía
    # PV→BESS se asigna a coste cero y por tanto NO genera ingreso PV.
    energy_to_grid_year = pv_to_grid_net_mwh * degradation_factor

    pv_opex_annual = inputs.pv.total_opex_annual
    annual_cash_flow = energy_to_grid_year * pv_price - pv_opex_annual
    discount_factors = (1.0 + discount) ** years
    discounted = annual_cash_flow / discount_factors

    pv_capex = inputs.pv.total_capex
    pv_van = float(-pv_capex + discounted.sum())
    pv_income_total = float((energy_to_grid_year * pv_price).sum())
    pv_lifetime_energy_mwh = float(energy_to_grid_year.sum())

    # Coste del curtailment (vida útil): ingreso PV perdido por la energía
    # recortada (POI físico + concurrencia), valorada al precio PV y descontada.
    curtail_year = pv_curtailment_total_mwh * degradation_factor
    pv_curtailment_cost_total = float(((curtail_year * pv_price) / discount_factors).sum())

    if pv_capex > 0:
        roi_total = pv_van / pv_capex
        pv_roi = float((1.0 + roi_total) ** (1.0 / lifespan) - 1.0) if roi_total > -1.0 else -1.0
    else:
        pv_roi = 0.0

    # --- Reconciliación energética PV↔BESS (sinergia, nivel anual) ---
    # Demanda anual de carga de la BESS: la energía que entrega (descarga) entre
    # el rendimiento de ciclo. La PV cubre una fracción f_PV de esa carga gratis.
    bess_discharge_year1 = _bess_annual_discharge_mwh(inputs, results)
    rte = max(inputs.efficiency.rte, 1e-6)
    bess_charge_demand_mwh = bess_discharge_year1 / rte

    pv_charges_bess = inputs.hybrid.charge_priority in ("pv_first", "mixed")
    if bess_charge_demand_mwh > 0 and pv_charges_bess:
        bess_solar_charge_mwh = min(pv_to_bess_mwh, bess_charge_demand_mwh)
        bess_solar_fraction = bess_solar_charge_mwh / bess_charge_demand_mwh
    else:
        bess_solar_charge_mwh = 0.0
        bess_solar_fraction = 0.0

    # Crédito de sinergia: la carga solar evita comprar esa energía en el pool
    # (precio de carga de red EVITADO). La PV se asigna a coste CERO, por lo que
    # el ahorro neto es el precio de carga evitado por MWh solar cargado. La
    # disponibilidad solar degrada año a año (degradación PV); se descuenta.
    grid_charge_price = float(cfg.get("bess_grid_charge_price", 35.0) or 0.0)
    synergy_year = bess_solar_charge_mwh * degradation_factor * grid_charge_price
    synergy_pv_charge_credit = float((synergy_year / discount_factors).sum())

    # Spread efectivo "vitaminado": el spread base más el ahorro de carga solar
    # repartido sobre la energía descargada por la BESS (presentación).
    base_spread = inputs.economic.avg_spread_price
    if bess_discharge_year1 > 0:
        effective_spread = base_spread + (bess_solar_charge_mwh * grid_charge_price) / bess_discharge_year1
    else:
        effective_spread = base_spread

    return HybridEconomics(
        pv_roi=pv_roi,
        pv_van=pv_van,
        pv_income_total=pv_income_total,
        pv_annual_energy_mwh=pv_annual_energy_mwh,
        pv_lifetime_energy_mwh=pv_lifetime_energy_mwh,
        pv_to_grid_mwh=pv_to_grid_mwh,
        pv_to_bess_mwh=pv_to_bess_mwh,
        pv_curtailed_mwh=pv_curtailed_mwh,
        pv_clipped_mwh=pv_clipped_mwh,
        poi_utilization_peak=inputs.poi_utilization_peak,
        pv_to_grid_net_mwh=pv_to_grid_net_mwh,
        pv_curtailed_concurrency_mwh=pv_curtailed_concurrency_mwh,
        pv_curtailment_total_mwh=pv_curtailment_total_mwh,
        pv_curtailment_cost_total=pv_curtailment_cost_total,
        bess_charge_demand_mwh=bess_charge_demand_mwh,
        bess_solar_charge_mwh=bess_solar_charge_mwh,
        bess_solar_fraction=bess_solar_fraction,
        bess_base_spread=base_spread,
        bess_effective_spread=effective_spread,
        synergy_pv_charge_credit=synergy_pv_charge_credit,
    )
