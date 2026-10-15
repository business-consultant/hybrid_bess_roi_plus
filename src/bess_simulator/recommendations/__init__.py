from __future__ import annotations
from dataclasses import dataclass

from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import SimulationResults
from bess_simulator.recommendations.decision_tree import (
    evaluate_roi,
    evaluate_degradation,
    RecommendationResult,
    DegradationResult,
)
from bess_simulator.recommendations.sub_recommendations import (
    evaluate_discount_rate,
    evaluate_opex,
    evaluate_rte,
    evaluate_lifespan,
    evaluate_retribution_price,
    SubRecommendation,
)
from bess_simulator.recommendations.alarms import check_historical_alarms, generate_alarm_message, Alarm


@dataclass
class FullRecommendation:
    roi_result: RecommendationResult
    degradation_result: DegradationResult
    sub_recommendations: list[SubRecommendation]
    alarms: list[Alarm]
    composite_message: str
    overall_color: str


# Términos naturales para cada parámetro revisable, usados al fusionar las
# sub-recomendaciones en una sola frase en lugar de pegar mensajes sueltos.
_SUB_TOPICS_ES = {
    "discount_rate": "la tasa de descuento aplicada",
    "opex": "el coste de mantenimiento (OPEX)",
    "rte": "el rendimiento de ciclo (RTE)",
    "lifespan": "la vida útil considerada",
    "retribution_price": "la retribución de mercado",
}

_SUB_TOPICS_EN = {
    "discount_rate": "the discount rate applied",
    "opex": "the maintenance cost (OPEX)",
    "rte": "the round-trip efficiency (RTE)",
    "lifespan": "the useful life considered",
    "retribution_price": "the market retribution price",
}

# Alias retrocompatible (código/tests existentes que importen el mapa en español).
_SUB_TOPICS = _SUB_TOPICS_ES


def _ensure_period(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text if text[-1] in ".!?" else text + "."


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _join_es(items: list[str]) -> str:
    """Une una lista en lenguaje natural: 'a', 'a y b', 'a, b y c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def _join_en(items: list[str]) -> str:
    """Joins a list in natural language: 'a', 'a and b', 'a, b and c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _compose_message(
    alarm_msg: str,
    roi_rec: RecommendationResult,
    deg_rec: DegradationResult,
    subs: list[SubRecommendation],
    lang: str = "es",
) -> str:
    """Construye un texto explicativo en lenguaje natural a partir de los
    distintos diagnósticos, encadenándolos con conectores en vez de
    concatenar mensajes independientes.

    Orden narrativo (de mayor a menor relevancia para el negocio):
      1. Veredicto de rentabilidad leído frente al coste del capital, con la
         dimensión estratégica cuando el ROI no lo justifica por sí solo.
      2. Consecuencia sobre la salud de la batería (SoH al fin de vida).
      3. Posición de los parámetros técnicos/económicos dentro de su rango,
         distinguiendo los que tienen margen de mejora de los que ya están en
         el límite aconsejado.
      4. Observación operativa: operación histórica fuera de rango.
    """
    en = lang == "en"
    sentences: list[str] = []

    # 1. Titular: veredicto de rentabilidad (ya incorpora la lectura frente al
    #    coste del capital y, si procede, la dimensión estratégica).
    sentences.append(_ensure_period(_upper_first(roi_rec.message)))

    # 2. Salud de la batería como matiz/consecuencia (cruce ROI × SoH).
    if deg_rec.message:
        if en:
            connector = "On the flip side, " if deg_rec.is_compromised else "On the technical side, "
        else:
            connector = "Como contrapartida, " if deg_rec.is_compromised else "Por el lado técnico, "
        sentences.append(_ensure_period(connector + _lower_first(deg_rec.message)))

    # 3. Parámetros técnicos/económicos: posición dentro de su rango.
    #    "margin" → queda recorrido de mejora · "limit" → en el borde del rango.
    margin = [s for s in subs if s.message and s.position == "margin"]
    at_limit = [s for s in subs if s.message and s.position == "limit"]

    topics_map = _SUB_TOPICS_EN if en else _SUB_TOPICS_ES
    join = _join_en if en else _join_es
    margin_topics = [topics_map.get(s.parameter, s.parameter) for s in margin]
    limit_topics = [topics_map.get(s.parameter, s.parameter) for s in at_limit]

    if limit_topics:
        if en:
            sentences.append(
                _ensure_period(
                    "It is worth taking a closer look at "
                    + join(limit_topics)
                    + ", already at the edge of the recommended range"
                )
            )
        else:
            sentences.append(
                _ensure_period(
                    "Conviene revisar con detalle "
                    + join(limit_topics)
                    + ", ya en el límite del rango aconsejado"
                )
            )
    if margin_topics:
        if en:
            sentences.append(
                _ensure_period(
                    "There is still room for improvement in " + join(margin_topics)
                )
            )
        else:
            sentences.append(
                _ensure_period(
                    "Aún queda margen de mejora en " + join(margin_topics)
                )
            )

    # 4. Observación operativa (histórico fuera de rango), al cierre.
    if alarm_msg:
        sentences.append(_ensure_period(alarm_msg))

    return " ".join(sentences)


def generate_full_recommendation(
    inputs: SimulationInputs,
    results: SimulationResults,
    advanced_config: dict | None = None,
    lang: str = "es",
) -> FullRecommendation:
    roi_rec = evaluate_roi(results.roi, inputs.economic.discount_rate, thresholds=advanced_config, lang=lang)

    soh_end_by_year = results.yearly_summary["soh_end"].tolist()
    last_year_degradation = 1.0 - soh_end_by_year[-1]
    deg_rec = evaluate_degradation(
        last_year_degradation,
        inputs.efficiency.soh_min,
        soh_end_by_year=soh_end_by_year,
        lang=lang,
    )

    subs = [
        evaluate_discount_rate(inputs.economic.discount_rate, cfg=advanced_config, lang=lang),
        evaluate_opex(inputs.economic.opex_per_mw_year, cfg=advanced_config, lang=lang),
        evaluate_rte(inputs.efficiency.rte, cfg=advanced_config, lang=lang),
        evaluate_lifespan(inputs.bess.lifespan_years, cfg=advanced_config, lang=lang),
        evaluate_retribution_price(inputs.economic.avg_spread_price, cfg=advanced_config, lang=lang),
    ]

    alarms = check_historical_alarms(results.interval_data, lang=lang)
    alarm_msg = generate_alarm_message(alarms, lang=lang)

    composite = _compose_message(alarm_msg, roi_rec, deg_rec, subs, lang=lang)

    # Color global de la tarjeta. Prioridad semántica:
    #   blue   → hay una consecuencia o compromiso a valorar por el operador
    #            (ROI por debajo del coste de capital / SoH al límite). Es
    #            informativo y agnóstico, nunca un "no recomendado".
    #   yellow → rentable pero con aspectos a vigilar.
    #   green  → rentable y sin alertas relevantes.
    colors = [roi_rec.color, deg_rec.color]
    if "blue" in colors:
        overall = "blue"
    elif "yellow" in colors:
        overall = "yellow"
    else:
        overall = "green"

    return FullRecommendation(
        roi_result=roi_rec,
        degradation_result=deg_rec,
        sub_recommendations=subs,
        alarms=alarms,
        composite_message=composite,
        overall_color=overall,
    )
