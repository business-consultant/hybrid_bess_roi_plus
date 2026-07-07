from __future__ import annotations
from dataclasses import dataclass
from bess_simulator.models.results import SimulationResults
from bess_simulator.models.parameters import SimulationInputs


@dataclass
class RecommendationResult:
    label: str
    color: str
    message: str
    # Lectura del ROI frente al coste del capital (≈ tasa de descuento):
    #   "above"    → ROI por encima de i
    #   "near"     → ROI en el entorno de i (banda de diversificación)
    #   "below"    → ROI positivo pero por debajo de i
    #   "negative" → ROI negativo
    vs_capital: str = "above"
    # True cuando la rentabilidad no justifica por sí sola la inversión y solo
    # tiene sentido por motivos estratégicos (ROI ≤ i). Es informativo, no
    # desaconseja: el operador puede asumirlo conscientemente.
    strategic: bool = False


def evaluate_roi(roi: float, discount_rate: float, thresholds: dict | None = None) -> RecommendationResult:
    """Evalúa ROI anualizado vs tasa de descuento (ambos tasas anuales).

    La tasa de descuento `i` se usa como referencia del coste del capital: un
    ROI por debajo de `i` significa que, en pura rentabilidad, el capital
    rendiría más en otra inversión de riesgo equivalente. No obstante, la BESS
    puede seguir teniendo sentido por motivos estratégicos, de cobertura o de
    servicio de red, de modo que el mensaje informa del compromiso sin
    desaconsejar.
    """
    from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG
    cfg = thresholds or DEFAULT_ADVANCED_CONFIG
    i = discount_rate
    high = cfg["rec_roi_high_threshold"]
    band = cfg["rec_roi_diversify_band"]

    if roi > i and roi > high:
        return RecommendationResult(
            "rentable", "green",
            "la inversión BESS es rentable y supera el coste del capital con holgura",
            vs_capital="above",
        )
    elif abs(roi - i) < band and roi > 0:
        return RecommendationResult(
            "rentable_diversificar", "yellow",
            "la inversión BESS es rentable, aunque su margen sobre el coste del "
            "capital es ajustado, por lo que conviene diversificar las fuentes de beneficio",
            vs_capital="near",
        )
    elif roi > i and roi <= high:
        return RecommendationResult(
            "moderada", "yellow",
            "la inversión BESS es rentable con un retorno moderado, por encima del coste del capital",
            vs_capital="above",
        )
    elif roi >= i and roi <= high:
        return RecommendationResult(
            "moderada", "yellow",
            "la inversión BESS es rentable con un retorno moderado, en línea con el coste del capital",
            vs_capital="near",
        )
    elif roi > 0 and roi < i:
        return RecommendationResult(
            "baja", "blue",
            "la rentabilidad de la BESS queda por debajo del coste del capital: en "
            "términos puramente financieros el capital rendiría más en otra inversión "
            "de riesgo similar, de modo que solo compensa si la instalación aporta "
            "valor estratégico (cobertura, servicios de red o posicionamiento)",
            vs_capital="below", strategic=True,
        )
    else:
        return RecommendationResult(
            "no_rentable", "blue",
            "con los parámetros actuales la inversión BESS no resulta rentable; solo "
            "tendría sentido asumirla por razones estratégicas o revisando las hipótesis del caso",
            vs_capital="negative", strategic=True,
        )


@dataclass
class DegradationResult:
    is_compromised: bool
    color: str
    message: str
    # Primer año (1-indexado) en que el SoH cae por debajo del mínimo
    # garantizado. None si nunca se incumple en el horizonte simulado.
    first_breach_year: int | None = None


def evaluate_degradation(
    last_year_degradation: float,
    soh_min: float,
    soh_end_by_year: "list[float] | None" = None,
) -> DegradationResult:
    """Evalúa si el ciclado compromete el SoH mínimo garantizado.

    Si se aporta `soh_end_by_year` (SoH al cierre de cada año del horizonte,
    en orden), se identifica el primer año en que el SoH baja del mínimo para
    informar al operador a partir de cuándo se incumple la garantía.
    """
    threshold = 1.0 - soh_min

    first_breach_year: int | None = None
    if soh_end_by_year is not None:
        for idx, soh in enumerate(soh_end_by_year):
            if soh < soh_min:
                first_breach_year = idx + 1  # año 1-indexado
                break

    if last_year_degradation >= threshold:
        if first_breach_year is not None:
            msg = (
                f"el ritmo de ciclado previsto lleva el SoH por debajo del mínimo "
                f"garantizado a partir del año {first_breach_year}, una consecuencia "
                f"a valorar frente a la rentabilidad obtenida"
            )
        else:
            msg = (
                "el ritmo de ciclado previsto llevará el SoH por debajo del mínimo "
                "recomendado al final de la vida útil, una consecuencia a valorar "
                "frente a la rentabilidad obtenida"
            )
        return DegradationResult(True, "blue", msg, first_breach_year=first_breach_year)
    else:
        return DegradationResult(
            False, "green",
            "queda margen de degradación antes de alcanzar el SoH mínimo, por lo que "
            "es posible ciclar algo más la batería para extraer más valor",
            first_breach_year=None,
        )

