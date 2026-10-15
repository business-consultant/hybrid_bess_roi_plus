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


def evaluate_discount_rate(rate: float, cfg: dict | None = None, lang: str = "es") -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    en = lang == "en"
    if rate < c["rec_discount_rate_ok"]:
        return SubRecommendation("discount_rate", "ok", "", position="optimal")
    elif rate <= c["rec_discount_rate_warning"]:
        msg = "It is recommended to review the discount rate used." if en else "Se recomienda revisar la tasa de descuento usada."
        return SubRecommendation("discount_rate", "warning", msg, position="margin")
    else:
        msg = ("It is recommended to review the discount rate used and assess whether a "
               "more favorable value applies.") if en else \
            "Se recomienda revisar la tasa de descuento usada y evaluar si es aplicable un valor más favorable."
        return SubRecommendation("discount_rate", "alert", msg, position="limit")


def evaluate_opex(opex_per_mw: float, cfg: dict | None = None, lang: str = "es") -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    en = lang == "en"
    if opex_per_mw < c["rec_opex_ok"]:
        return SubRecommendation("opex", "ok", "", position="optimal")
    elif opex_per_mw <= c["rec_opex_warning"]:
        msg = "It is recommended to review the maintenance cost." if en else "Se recomienda revisar el coste de mantenimiento."
        return SubRecommendation("opex", "warning", msg, position="margin")
    else:
        msg = ("It is recommended to review the maintenance cost and assess whether a "
               "more favorable value applies.") if en else \
            "Se recomienda revisar el coste de mantenimiento y evaluar si es aplicable un valor más favorable."
        return SubRecommendation("opex", "alert", msg, position="limit")


def evaluate_rte(rte: float, cfg: dict | None = None, lang: str = "es") -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    en = lang == "en"
    if rte >= c["rec_rte_ok"]:
        return SubRecommendation("rte", "ok", "", position="optimal")
    elif rte >= c["rec_rte_warning"]:
        msg = "It is recommended to review the Round Trip Efficiency." if en else "Se recomienda revisar el Round Trip Efficiency."
        return SubRecommendation("rte", "warning", msg, position="margin")
    else:
        msg = ("It is recommended to review the Round Trip Efficiency and assess whether "
               "a more favorable value applies.") if en else \
            "Se recomienda revisar el Round Trip Efficiency y evaluar si es aplicable un valor más favorable."
        return SubRecommendation("rte", "alert", msg, position="limit")


def evaluate_lifespan(years: int, cfg: dict | None = None, lang: str = "es") -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    en = lang == "en"
    if years >= c["rec_lifespan_ok"]:
        return SubRecommendation("lifespan", "ok", "", position="optimal")
    elif years >= c["rec_lifespan_warning"]:
        msg = "Consider increasing the useful life of your BESS installation." if en else "Considere aumentar la vida útil de su instalación BESS."
        return SubRecommendation("lifespan", "warning", msg, position="margin")
    else:
        msg = "It is recommended to increase the useful life of your BESS installation." if en else "Se recomienda aumentar la vida útil de su instalación BESS."
        return SubRecommendation("lifespan", "alert", msg, position="limit")


def evaluate_retribution_price(price: float, cfg: dict | None = None, lang: str = "es") -> SubRecommendation:
    c = cfg or DEFAULT_ADVANCED_CONFIG
    en = lang == "en"
    if price > c["rec_price_ok"]:
        return SubRecommendation("retribution_price", "ok", "", position="optimal")
    elif price >= c["rec_price_warning"]:
        msg = "The average retribution price suggests reviewing market strategies." if en else "La retribución promedio sugiere revisar estrategias de mercado."
        return SubRecommendation("retribution_price", "warning", msg, position="margin")
    else:
        msg = ("The average retribution price suggests reviewing buy/sell energy "
               "strategies and/or considering new markets.") if en else \
            "La retribución promedio sugiere revisar las estrategias de compra y venta de energía y/o considerar nuevos mercados."
        return SubRecommendation("retribution_price", "alert", msg, position="limit")
