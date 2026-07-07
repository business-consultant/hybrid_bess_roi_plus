from dataclasses import dataclass, field

import pandas as pd


@dataclass
class RevenueBreakdown:
    """Desglose de los ingresos del BESS por stream (totales de vida útil, €).

    I_BESS = arbitraje + PPA + capacidad + secundaria. Los streams activos
    dependen del :class:`RevenueModel` seleccionado por el operador.
    """

    arbitrage: float = 0.0
    ppa: float = 0.0
    capacity: float = 0.0
    secondary: float = 0.0

    @property
    def total(self) -> float:
        return self.arbitrage + self.ppa + self.capacity + self.secondary


@dataclass
class HybridEconomics:
    """Economía de la PV y flujos híbridos en el POI.

    El ROI/VAN de la PV es INDEPENDIENTE del de la BESS (no comparten CAPEX).
    Los flujos están medidos sobre un año representativo (energía en MWh).
    """

    # Economía PV (vida útil)
    pv_roi: float = 0.0
    pv_van: float = 0.0
    pv_income_total: float = 0.0
    pv_annual_energy_mwh: float = 0.0      # energía AC año 1 (bornes inversor)
    pv_lifetime_energy_mwh: float = 0.0
    # Flujos híbridos en el POI (año representativo, MWh)
    pv_to_grid_mwh: float = 0.0
    pv_to_bess_mwh: float = 0.0
    pv_curtailed_mwh: float = 0.0
    pv_clipped_mwh: float = 0.0            # recorte DC del inversor (ILR)
    poi_utilization_peak: float = 0.0

    # Reconciliación energética PV↔BESS (año representativo)
    pv_to_grid_net_mwh: float = 0.0       # inyección directa NETA tras curtailment
    pv_curtailed_concurrency_mwh: float = 0.0  # recorte por concurrencia POI
    pv_curtailment_total_mwh: float = 0.0      # curtailment total año 1 (POI+concurrencia)
    pv_curtailment_cost_total: float = 0.0     # ingreso PV perdido por curtailment (vida útil, €)
    bess_charge_demand_mwh: float = 0.0   # energía anual que la BESS necesita cargar
    bess_solar_charge_mwh: float = 0.0    # PV→BESS efectiva usada como carga (acotada)
    bess_solar_fraction: float = 0.0      # f_PV: fracción de carga BESS de origen solar
    bess_base_spread: float = 0.0         # spread base (€/MWh)
    bess_effective_spread: float = 0.0    # spread vitaminado por carga solar gratis
    synergy_pv_charge_credit: float = 0.0  # crédito de sinergia PV→BESS (vida útil, €, descontado)


@dataclass
class PlantSummary:
    """Resumen agregado de la planta híbrida para la pantalla general (Fase 6).

    Reúne especificaciones del activo, energía entregada en el periodo y los
    KPIs operativos que alimentan la vista tipo panel de control (Bluence).
    """

    # Especificaciones del activo
    location: str = "—"
    nominal_power_mw: float = 0.0
    bess_capacity_mwh: float = 0.0
    pv_peak_mwp: float = 0.0
    pv_inverter_mw: float = 0.0
    ilr: float = 0.0
    poi_limit_mw: float = 0.0

    # Energía entregada en el periodo
    exported_gwh: float = 0.0
    imported_gwh: float = 0.0
    pv_generated_gwh: float = 0.0
    net_mwh: float = 0.0
    exported_pct: float = 0.0
    imported_pct: float = 0.0

    # KPIs operativos
    time_based_availability: float = 0.0   # %
    soc_min_pct: float = 0.0
    soc_max_pct: float = 0.0
    roundtrip_efficiency: float = 0.0      # fracción (0..1)
    cycle_count: float = 0.0
    state_of_health: float = 0.0           # fracción (0..1)
    charge_discharge_avg_power_mw: float = 0.0

    # KPIs fotovoltaicos
    pv_capacity_factor: float = 0.0        # fracción (0..1), base AC del inversor
    pv_performance_ratio: float = 0.0      # fracción (0..1), IEC 61724
    pv_availability: float = 0.0           # % de horas de sol con producción
    pv_irradiation_wh_m2: float = 0.0      # irradiación POA acumulada (Wh/m²)
    pv_production_mwh: float = 0.0         # energía PV AC entregada (MWh)
    pv_clearsky_wh_m2: float = 0.0         # irradiación de cielo claro (referencia)
    pv_period_hours: float = 0.0           # horas del periodo PV (para desvíos)

    # Recuento de subelementos (acceso a monitorización)
    meters: int = 0
    pcs: int = 0
    bess_modules: int = 0
    power_stations: int = 0


@dataclass
class SimulationResults:
    roi: float
    van: float
    interval_data: pd.DataFrame  # Columns: timestamp (15-min), available_capacity, period_degradation, cycle_number, rte, sold_energy, spread_price, income, interval_opex, cash_flow, discounted_cf, accumulated_dcf
    yearly_summary: pd.DataFrame  # Columns: year, total_income, total_opex, net_cash_flow, accumulated_dcf, avg_degradation, avg_rte, soh_compliance (bool)
    total_incumplimientos: int  # count of intervals where degradation > (1 - soh_min)
    revenue_breakdown: RevenueBreakdown = field(default_factory=RevenueBreakdown)
    hybrid: HybridEconomics | None = None


@dataclass
class SensitivityResult:
    matrix: pd.DataFrame
    opex_values: list[float]
    price_values: list[float]
