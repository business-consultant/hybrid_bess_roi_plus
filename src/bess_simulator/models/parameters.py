from dataclasses import dataclass, field
from enum import Enum

from bess_simulator.config import DEFAULTS, INTERVALS_PER_DAY, RANGES


class RevenueModel(str, Enum):
    """Modelos de negocio/ingresos del BESS, en capas acumulativas.

    Cada escenario añade un stream sobre el anterior:
      a) ARBITRAGE                      → solo arbitraje
      b) ARBITRAGE_PPA                  → + PPA a precio fijo
      c) ARBITRAGE_PPA_CAPACITY         → + pago por capacidad
      d) ARBITRAGE_PPA_CAPACITY_SECONDARY → + regulación secundaria
    """

    ARBITRAGE = "a_arbitrage"
    ARBITRAGE_PPA = "b_arbitrage_ppa"
    ARBITRAGE_PPA_CAPACITY = "c_arbitrage_ppa_capacity"
    ARBITRAGE_PPA_CAPACITY_SECONDARY = "d_arbitrage_ppa_capacity_secondary"

    @property
    def has_ppa(self) -> bool:
        return self in (
            RevenueModel.ARBITRAGE_PPA,
            RevenueModel.ARBITRAGE_PPA_CAPACITY,
            RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
        )

    @property
    def has_capacity(self) -> bool:
        return self in (
            RevenueModel.ARBITRAGE_PPA_CAPACITY,
            RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY,
        )

    @property
    def has_secondary(self) -> bool:
        return self is RevenueModel.ARBITRAGE_PPA_CAPACITY_SECONDARY


def _check_range(name: str, value: float) -> None:
    if name not in RANGES:
        return
    lo, hi = RANGES[name]
    if not (lo <= value <= hi):
        raise ValueError(f"{name}={value} fuera del rango permitido [{lo}, {hi}]")


@dataclass
class EconomicParams:
    capex_per_mw: float = DEFAULTS["capex_per_mw"]
    opex_per_mw_year: float = DEFAULTS["opex_per_mw_year"]
    discount_rate: float = DEFAULTS["discount_rate"]
    avg_spread_price: float = DEFAULTS["avg_spread_price"]
    tax_rate: float = DEFAULTS["tax_rate"]
    inflation_rate: float = DEFAULTS["inflation_rate"]

    def __post_init__(self) -> None:
        for name in ("capex_per_mw", "opex_per_mw_year", "discount_rate", "avg_spread_price"):
            _check_range(name, getattr(self, name))


@dataclass
class BessParams:
    rated_power_mw: float = DEFAULTS["rated_power_mw"]
    c_rate_inverse: float = DEFAULTS["c_rate_inverse"]
    nominal_power: float = DEFAULTS["nominal_power"]
    eqo_cycles: float = DEFAULTS["eqo_cycles"]
    lifespan_years: int = int(DEFAULTS["lifespan_years"])

    def __post_init__(self) -> None:
        for name in ("rated_power_mw", "c_rate_inverse", "eqo_cycles", "lifespan_years"):
            _check_range(name, getattr(self, name))


@dataclass
class EfficiencyParams:
    initial_soh: float = DEFAULTS["initial_soh"]
    rte: float = DEFAULTS["rte"]
    degradation_per_cycle: float = DEFAULTS["degradation_per_cycle"]
    soh_min: float = DEFAULTS["soh_min"]
    max_dod: float = DEFAULTS["max_dod"]
    min_soc: float = DEFAULTS["min_soc"]

    def __post_init__(self) -> None:
        for name in ("initial_soh", "rte", "degradation_per_cycle", "soh_min", "max_dod", "min_soc"):
            _check_range(name, getattr(self, name))


@dataclass
class ActivityParams:
    year_cycles: float = DEFAULTS["year_cycles"]

    def __post_init__(self) -> None:
        _check_range("year_cycles", self.year_cycles)


@dataclass
class PvParams:
    """Parámetros de la planta fotovoltaica hibridada.

    El ROI de la BESS NO incluye el CAPEX/OPEX de la PV; estos campos se usan
    para el ROI independiente de la PV y para el dimensionado del POI.
    """

    peak_power_mwp: float = DEFAULTS["pv_peak_power_mwp"]
    inverter_ac_mw: float = DEFAULTS["pv_inverter_ac_mw"]
    performance_ratio: float = DEFAULTS["pv_performance_ratio"]
    annual_degradation: float = DEFAULTS["pv_annual_degradation"]
    soiling_loss: float = DEFAULTS["pv_soiling_loss"]
    capex_per_mwp: float = DEFAULTS["pv_capex_per_mwp"]
    opex_per_mwp_year: float = DEFAULTS["pv_opex_per_mwp_year"]
    latitude: float = DEFAULTS["pv_latitude"]

    def __post_init__(self) -> None:
        for name, attr in (
            ("pv_peak_power_mwp", "peak_power_mwp"),
            ("pv_inverter_ac_mw", "inverter_ac_mw"),
            ("pv_performance_ratio", "performance_ratio"),
            ("pv_annual_degradation", "annual_degradation"),
            ("pv_soiling_loss", "soiling_loss"),
            ("pv_capex_per_mwp", "capex_per_mwp"),
            ("pv_opex_per_mwp_year", "opex_per_mwp_year"),
            ("pv_latitude", "latitude"),
        ):
            _check_range(name, getattr(self, attr))

    @property
    def dc_ac_ratio(self) -> float:
        """Inverter Loading Ratio (ILR) = MWp / MW_ac."""
        return self.peak_power_mwp / self.inverter_ac_mw

    @property
    def total_capex(self) -> float:
        return self.capex_per_mwp * self.peak_power_mwp

    @property
    def total_opex_annual(self) -> float:
        return self.opex_per_mwp_year * self.peak_power_mwp


@dataclass
class GridParams:
    """Punto de interconexión (POI) compartido PV+BESS."""

    poi_limit_mw: float = DEFAULTS["poi_limit_mw"]
    curtailment_allowed: bool = True
    curtailment_price: float = DEFAULTS["curtailment_price"]

    def __post_init__(self) -> None:
        _check_range("poi_limit_mw", self.poi_limit_mw)
        _check_range("curtailment_price", self.curtailment_price)


@dataclass
class HybridParams:
    """Estrategia de operación de la planta híbrida."""

    charge_priority: str = "pv_first"  # pv_first | grid | mixed
    pv_to_bess_share: float = DEFAULTS["pv_to_bess_share"]

    def __post_init__(self) -> None:
        _check_range("pv_to_bess_share", self.pv_to_bess_share)


@dataclass
class RevenueParams:
    """Parámetros de los streams de ingreso adicionales al arbitraje.

    El stream activo depende de :class:`RevenueModel`.
    """

    model: RevenueModel = RevenueModel.ARBITRAGE
    ppa_price: float = DEFAULTS["ppa_price"]
    ppa_energy_share: float = DEFAULTS["ppa_energy_share"]
    capacity_price_eur_mw_year: float = DEFAULTS["capacity_price_eur_mw_year"]
    committed_mw: float = DEFAULTS["committed_mw"]
    secondary_band_up_mw: float = DEFAULTS["secondary_band_up_mw"]
    secondary_band_down_mw: float = DEFAULTS["secondary_band_down_mw"]
    secondary_price: float = DEFAULTS["secondary_price"]
    secondary_activation_rate: float = DEFAULTS["secondary_activation_rate"]

    def __post_init__(self) -> None:
        for name, attr in (
            ("ppa_price", "ppa_price"),
            ("ppa_energy_share", "ppa_energy_share"),
            ("capacity_price_eur_mw_year", "capacity_price_eur_mw_year"),
            ("committed_mw", "committed_mw"),
            ("secondary_band_up_mw", "secondary_band_up_mw"),
            ("secondary_band_down_mw", "secondary_band_down_mw"),
            ("secondary_price", "secondary_price"),
            ("secondary_activation_rate", "secondary_activation_rate"),
        ):
            _check_range(name, getattr(self, attr))

    @property
    def secondary_band_total_mw(self) -> float:
        """Banda total reservada (subir + bajar). Igual a 2·banda si es simétrica."""
        return self.secondary_band_up_mw + self.secondary_band_down_mw


@dataclass
class SimulationInputs:
    economic: EconomicParams = field(default_factory=EconomicParams)
    bess: BessParams = field(default_factory=BessParams)
    efficiency: EfficiencyParams = field(default_factory=EfficiencyParams)
    activity: ActivityParams = field(default_factory=ActivityParams)
    pv: PvParams = field(default_factory=PvParams)
    grid: GridParams = field(default_factory=GridParams)
    hybrid: HybridParams = field(default_factory=HybridParams)
    revenue: RevenueParams = field(default_factory=RevenueParams)

    @property
    def total_capacity_mwh(self) -> float:
        return self.bess.rated_power_mw * self.bess.c_rate_inverse

    @property
    def output_power_mw(self) -> float:
        return self.bess.rated_power_mw * self.bess.nominal_power

    @property
    def total_capex(self) -> float:
        return self.economic.capex_per_mw * self.bess.rated_power_mw

    @property
    def total_opex_annual(self) -> float:
        return self.economic.opex_per_mw_year * self.bess.rated_power_mw

    @property
    def daily_opex(self) -> float:
        return self.total_opex_annual / 365

    @property
    def interval_opex(self) -> float:
        return self.total_opex_annual / (365 * INTERVALS_PER_DAY)

    @property
    def daily_cycles(self) -> float:
        return self.activity.year_cycles / 365

    @property
    def interval_cycles(self) -> float:
        return self.activity.year_cycles / (365 * INTERVALS_PER_DAY)

    @property
    def monthly_cycles(self) -> float:
        return self.activity.year_cycles / 12

    @property
    def initial_degradation(self) -> float:
        return 1.0 - self.efficiency.initial_soh

    # --- Derivados de hibridación (PV + POI) ---
    @property
    def pv_dc_ac_ratio(self) -> float:
        return self.pv.dc_ac_ratio

    @property
    def pv_to_bess_ratio(self) -> float:
        """Relación de dimensionado PV (MWp) / BESS (MW)."""
        return self.pv.peak_power_mwp / self.bess.rated_power_mw

    @property
    def poi_utilization_peak(self) -> float:
        """Ratio potencia AC máxima conjunta PV+BESS frente al límite del POI.

        > 1.0 indica solapamiento potencial → oportunidad de arbitraje del
        clipping PV hacia la BESS y/o curtailment.
        """
        combined_ac = self.pv.inverter_ac_mw + self.output_power_mw
        return combined_ac / self.grid.poi_limit_mw

    @property
    def pv_total_capex(self) -> float:
        return self.pv.total_capex

    @property
    def pv_total_opex_annual(self) -> float:
        return self.pv.total_opex_annual
