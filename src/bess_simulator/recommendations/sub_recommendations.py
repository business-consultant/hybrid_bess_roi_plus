from __future__ import annotations
from dataclasses import dataclass

from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG


@dataclass
class SubRecommendation:
    parameter: str
    level: str
    message: str
    # Lectura de posición dentro del rango del parámetro. No es un veredicto
    # ok/mal, sino dónde se sitúa el valor respecto a su recorrido útil:
    #   "optimal" → ya en zona óptima, sin margen relevante de mejora
    #   "margin"  → aceptable, pero queda recorrido de mejora
    #   "limit"   → en el límite del rango aconsejado, conviene actuar
    position: str = "optimal"


def evaluate_discount_rate(rate: float, cfg: dict | None = None) -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    if rate < c["rec_discount_rate_ok"]:
        return SubRecommendation("discount_rate", "ok", "", position="optimal")
    elif rate <= c["rec_discount_rate_warning"]:
        return SubRecommendation("discount_rate", "warning", "Se recomienda revisar la tasa de descuento usada.", position="margin")
    else:
        return SubRecommendation("discount_rate", "alert", "Se recomienda revisar la tasa de descuento usada y evaluar si es aplicable un valor más favorable.", position="limit")


def evaluate_opex(opex_per_mw: float, cfg: dict | None = None) -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    if opex_per_mw < c["rec_opex_ok"]:
        return SubRecommendation("opex", "ok", "", position="optimal")
    elif opex_per_mw <= c["rec_opex_warning"]:
        return SubRecommendation("opex", "warning", "Se recomienda revisar el coste de mantenimiento.", position="margin")
    else:
        return SubRecommendation("opex", "alert", "Se recomienda revisar el coste de mantenimiento y evaluar si es aplicable un valor más favorable.", position="limit")


def evaluate_rte(rte: float, cfg: dict | None = None) -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    if rte >= c["rec_rte_ok"]:
        return SubRecommendation("rte", "ok", "", position="optimal")
    elif rte >= c["rec_rte_warning"]:
        return SubRecommendation("rte", "warning", "Se recomienda revisar el Round Trip Efficiency.", position="margin")
    else:
        return SubRecommendation("rte", "alert", "Se recomienda revisar el Round Trip Efficiency y evaluar si es aplicable un valor más favorable.", position="limit")


def evaluate_lifespan(years: int, cfg: dict | None = None) -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    if years >= c["rec_lifespan_ok"]:
        return SubRecommendation("lifespan", "ok", "", position="optimal")
    elif years >= c["rec_lifespan_warning"]:
        return SubRecommendation("lifespan", "warning", "Considere aumentar la vida útil de su instalación BESS.", position="margin")
    else:
        return SubRecommendation("lifespan", "alert", "Se recomienda aumentar la vida útil de su instalación BESS.", position="limit")


def evaluate_retribution_price(price: float, cfg: dict | None = None) -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    if price > c["rec_price_ok"]:
        return SubRecommendation("retribution_price", "ok", "", position="optimal")
    elif price >= c["rec_price_warning"]:
        return SubRecommendation("retribution_price", "warning", "La retribución promedio sugiere revisar estrategias de mercado.", position="margin")
    else:
        return SubRecommendation("retribution_price", "alert", "La retribución promedio sugiere revisar las estrategias de compra y venta de energía y/o considerar nuevos mercados.", position="limit")

