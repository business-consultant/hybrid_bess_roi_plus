"""Tests del motor de recomendaciones.

Cubre dos niveles:

1. **Unitarios por rama**: cada salida de `evaluate_roi`, `evaluate_degradation`
   y las sub-recomendaciones, más el narrador `_compose_message`.
2. **Consistencia sobre el universo de posibilidades**: barridos exhaustivos
   sobre los rangos válidos (`config.RANGES`) que verifican invariantes que
   deben cumplirse para CUALQUIER combinación de entradas, de modo que la
   recomendación nunca quede en un estado incoherente.

Referencia normativa: docs/02-design/motor-recomendaciones.md
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from bess_simulator.config import RANGES
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG
from bess_simulator.models.parameters import SimulationInputs
from bess_simulator.models.results import SimulationResults
from bess_simulator.recommendations import (
    generate_full_recommendation,
    _compose_message,
    _ensure_period,
    _upper_first,
    _lower_first,
    _join_es,
)
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

# Conjuntos válidos de valores categóricos del motor.
ROI_COLORS = {"green", "yellow", "blue"}
ROI_VS_CAPITAL = {"above", "near", "below", "negative"}
DEG_COLORS = {"green", "blue"}
SUB_LEVELS = {"ok", "warning", "alert"}
SUB_POSITIONS = {"optimal", "margin", "limit"}
OVERALL_COLORS = {"green", "yellow", "blue"}

# Correspondencia normativa nivel ↔ posición de las sub-recomendaciones.
LEVEL_TO_POSITION = {"ok": "optimal", "warning": "margin", "alert": "limit"}


def _grid(name: str, n: int = 25) -> np.ndarray:
    """Malla de valores que cubre con holgura el rango del parámetro."""
    lo, hi = RANGES[name]
    span = hi - lo
    # Se extiende ligeramente por debajo/encima para ejercitar los extremos.
    return np.linspace(lo - 0.05 * span, hi + 0.05 * span, n)


# ---------------------------------------------------------------------------
# 1. evaluate_roi — ramas individuales
# ---------------------------------------------------------------------------
class TestEvaluateRoi:
    def test_rentable_holgado(self):
        r = evaluate_roi(0.20, 0.06)
        assert r.color == "green"
        assert r.label == "rentable"
        assert r.vs_capital == "above"
        assert r.strategic is False

    def test_diversificar_margen_ajustado(self):
        # ROI dentro de la banda alrededor de i → "near".
        r = evaluate_roi(0.065, 0.06)
        assert r.color == "yellow"
        assert r.label == "rentable_diversificar"
        assert r.vs_capital == "near"

    def test_moderada_por_encima(self):
        # Por encima de i pero por debajo del umbral alto, fuera de la banda.
        r = evaluate_roi(0.075, 0.05)
        assert r.color == "yellow"
        assert r.label == "moderada"
        assert r.vs_capital == "above"

    def test_baja_por_debajo_del_capital_es_estrategica(self):
        r = evaluate_roi(0.03, 0.08)
        assert r.color == "blue"
        assert r.label == "baja"
        assert r.vs_capital == "below"
        assert r.strategic is True

    def test_no_rentable_es_estrategica_no_prohibitiva(self):
        r = evaluate_roi(-0.05, 0.06)
        assert r.color == "blue"
        assert r.label == "no_rentable"
        assert r.vs_capital == "negative"
        assert r.strategic is True

    def test_no_usa_color_rojo_ni_desaconseja(self):
        # Ningún caso debe ser "rojo" ni contener lenguaje prohibitivo.
        for roi in (-0.2, -0.01, 0.0, 0.03, 0.06, 0.09, 0.5):
            r = evaluate_roi(roi, 0.06)
            assert r.color != "red"
            assert "no recomendado" not in r.message.lower()

    def test_respeta_umbrales_de_config(self):
        cfg = dict(DEFAULT_ADVANCED_CONFIG)
        cfg["rec_roi_high_threshold"] = 0.15
        # ROI 0.10 con high=0.15 y lejos de i=0.04 → moderada (no rentable holgado).
        r = evaluate_roi(0.10, 0.04, thresholds=cfg)
        assert r.label == "moderada"
        assert r.color == "yellow"


# ---------------------------------------------------------------------------
# 2. evaluate_degradation — con y sin año de incumplimiento
# ---------------------------------------------------------------------------
class TestEvaluateDegradation:
    def test_con_margen(self):
        # Degradación pequeña, SoH siempre por encima del mínimo.
        soh = [1.0, 0.98, 0.96, 0.94]
        r = evaluate_degradation(0.04, soh_min=0.75, soh_end_by_year=soh)
        assert r.is_compromised is False
        assert r.color == "green"
        assert r.first_breach_year is None

    def test_compromiso_con_anio_de_incumplimiento(self):
        # SoH cruza el mínimo (0.75) en el año 4 (índice 3).
        soh = [0.95, 0.88, 0.80, 0.74, 0.70]
        last_deg = 1.0 - soh[-1]
        r = evaluate_degradation(last_deg, soh_min=0.75, soh_end_by_year=soh)
        assert r.is_compromised is True
        assert r.color == "blue"
        assert r.first_breach_year == 4
        assert "año 4" in r.message

    def test_compromiso_sin_serie_anual(self):
        r = evaluate_degradation(0.30, soh_min=0.75, soh_end_by_year=None)
        assert r.is_compromised is True
        assert r.color == "blue"
        assert r.first_breach_year is None
        assert "vida útil" in r.message

    def test_primer_anio_es_el_primero_que_cruza(self):
        # Aunque varios años incumplan, se reporta el primero.
        soh = [0.90, 0.74, 0.73, 0.60]
        r = evaluate_degradation(1.0 - soh[-1], soh_min=0.75, soh_end_by_year=soh)
        assert r.first_breach_year == 2


# ---------------------------------------------------------------------------
# 3. Sub-recomendaciones — posición margen/límite
# ---------------------------------------------------------------------------
class TestSubRecommendations:
    def test_discount_rate_posiciones(self):
        assert evaluate_discount_rate(0.05).position == "optimal"
        assert evaluate_discount_rate(0.09).position == "margin"
        assert evaluate_discount_rate(0.14).position == "limit"

    def test_opex_posiciones(self):
        assert evaluate_opex(8_000).position == "optimal"
        assert evaluate_opex(12_000).position == "margin"
        assert evaluate_opex(20_000).position == "limit"

    def test_rte_posiciones(self):
        assert evaluate_rte(0.90).position == "optimal"
        assert evaluate_rte(0.83).position == "margin"
        assert evaluate_rte(0.78).position == "limit"

    def test_lifespan_posiciones(self):
        assert evaluate_lifespan(20).position == "optimal"
        assert evaluate_lifespan(12).position == "margin"
        assert evaluate_lifespan(8).position == "limit"

    def test_price_posiciones(self):
        assert evaluate_retribution_price(50).position == "optimal"
        assert evaluate_retribution_price(35).position == "margin"
        assert evaluate_retribution_price(25).position == "limit"

    def test_optimal_no_genera_mensaje(self):
        assert evaluate_opex(8_000).message == ""
        assert evaluate_rte(0.90).message == ""


# ---------------------------------------------------------------------------
# 4. Narrador (_compose_message y utilidades)
# ---------------------------------------------------------------------------
class TestNarrador:
    def test_ensure_period(self):
        assert _ensure_period("hola") == "hola."
        assert _ensure_period("hola.") == "hola."
        assert _ensure_period("  ") == ""

    def test_upper_lower_first(self):
        assert _upper_first("hola") == "Hola"
        assert _lower_first("Hola") == "hola"
        assert _upper_first("") == ""

    def test_join_es(self):
        assert _join_es([]) == ""
        assert _join_es(["a"]) == "a"
        assert _join_es(["a", "b"]) == "a y b"
        assert _join_es(["a", "b", "c"]) == "a, b y c"

    def test_mensaje_es_prosa_no_concatenacion(self):
        roi = evaluate_roi(0.065, 0.06)
        deg = evaluate_degradation(0.30, 0.75, soh_end_by_year=[0.9, 0.8, 0.74])
        subs = [evaluate_opex(20_000), evaluate_rte(0.78)]
        msg = _compose_message("", roi, deg, subs)
        # Nunca el viejo separador "+".
        assert " + " not in msg
        # Empieza en mayúscula y acaba en punto.
        assert msg[0].isupper()
        assert msg.endswith(".")
        # Cita los temas en lenguaje natural, no las claves técnicas.
        assert "OPEX" in msg
        assert "rendimiento de ciclo" in msg

    def test_limite_y_margen_en_frases_separadas(self):
        roi = evaluate_roi(0.20, 0.06)
        deg = evaluate_degradation(0.04, 0.75, soh_end_by_year=[1.0, 0.98])
        subs = [evaluate_opex(20_000), evaluate_rte(0.83)]  # uno limit, uno margin
        msg = _compose_message("", roi, deg, subs)
        assert "en el límite del rango aconsejado" in msg
        assert "margen de mejora" in msg

    def test_alarma_se_anexa_al_cierre(self):
        roi = evaluate_roi(0.20, 0.06)
        deg = evaluate_degradation(0.04, 0.75, soh_end_by_year=[1.0])
        msg = _compose_message("Aviso histórico de prueba", roi, deg, [])
        assert msg.strip().endswith("Aviso histórico de prueba.")


# ---------------------------------------------------------------------------
# Helper para integración: construye SimulationResults mínimos.
# ---------------------------------------------------------------------------
def _make_results(roi: float, soh_end_by_year: list[float], rte_value: float = 0.85) -> SimulationResults:
    n = 96
    interval = pd.DataFrame({
        "rte": np.full(n, rte_value),  # dentro de [0.80, 0.90] → sin alarma
    })
    yearly = pd.DataFrame({
        "year": list(range(len(soh_end_by_year))),
        "soh_end": soh_end_by_year,
    })
    return SimulationResults(
        roi=roi,
        van=0.0,
        interval_data=interval,
        yearly_summary=yearly,
        total_incumplimientos=0,
    )


# ---------------------------------------------------------------------------
# 5. Integración: generate_full_recommendation
# ---------------------------------------------------------------------------
class TestFullRecommendation:
    def test_estructura_basica(self):
        inputs = SimulationInputs()
        results = _make_results(0.07, [1.0, 0.98, 0.96])
        rec = generate_full_recommendation(inputs, results)
        assert rec.overall_color in OVERALL_COLORS
        assert rec.composite_message
        assert rec.roi_result is not None
        assert rec.degradation_result is not None
        assert len(rec.sub_recommendations) == 5

    def test_color_global_blue_si_roi_estrategico(self):
        inputs = SimulationInputs()  # discount_rate 0.06
        results = _make_results(-0.02, [1.0, 0.99])  # ROI negativo
        rec = generate_full_recommendation(inputs, results)
        assert rec.overall_color == "blue"

    def test_anio_incumplimiento_en_mensaje(self):
        inputs = SimulationInputs()  # soh_min 0.75
        # SoH cruza 0.75 en el año 3.
        results = _make_results(0.20, [0.90, 0.80, 0.70, 0.65])
        rec = generate_full_recommendation(inputs, results)
        assert rec.degradation_result.first_breach_year == 3
        assert "año 3" in rec.composite_message


# ---------------------------------------------------------------------------
# 6. CONSISTENCIA — barridos sobre el universo de posibilidades
# ---------------------------------------------------------------------------
class TestConsistencyUniverse:
    def test_roi_invariantes_en_toda_la_malla(self):
        """Para cualquier (ROI, i) válidos los invariantes se mantienen."""
        rois = np.linspace(-0.5, 1.0, 60)
        discounts = _grid("discount_rate", 12)
        for roi, i in itertools.product(rois, discounts):
            r = evaluate_roi(float(roi), float(i))
            # Dominios cerrados.
            assert r.color in ROI_COLORS
            assert r.vs_capital in ROI_VS_CAPITAL
            assert r.message and r.message == r.message.strip()
            # strategic ⇔ color azul (informativo, nunca prohibitivo).
            assert (r.color == "blue") == bool(r.strategic)
            # Nunca rojo ni lenguaje de prohibición.
            assert r.color != "red"
            assert "no recomendado" not in r.message.lower()
            # Coherencia de la lectura frente al capital:
            #   verde ⇒ por encima del capital; estratégico ⇒ por debajo/negativo.
            if r.color == "green":
                assert r.vs_capital == "above"
            if r.strategic:
                assert r.vs_capital in {"below", "negative"}

    def test_roi_extremos_deterministas(self):
        # ROI muy alto siempre verde; ROI negativo siempre azul/estratégico.
        for i in _grid("discount_rate", 10):
            assert evaluate_roi(5.0, float(i)).color == "green"
            neg = evaluate_roi(-0.3, float(i))
            assert neg.color == "blue" and neg.strategic is True

    def test_degradacion_invariantes(self):
        """El año reportado es siempre el primero por debajo del mínimo."""
        soh_min = 0.75
        # Genera muchas trayectorias SoH monótonas decrecientes variadas.
        rng = np.random.default_rng(20260616)
        for _ in range(300):
            n = int(rng.integers(2, 26))
            start = float(rng.uniform(0.95, 1.0))
            drop = float(rng.uniform(0.005, 0.06))
            soh = list(np.clip(start - drop * np.arange(n), 0.4, 1.0))
            last_deg = 1.0 - soh[-1]
            r = evaluate_degradation(last_deg, soh_min, soh_end_by_year=soh)

            assert r.color in DEG_COLORS
            assert r.is_compromised == (r.color == "blue")

            below = [idx for idx, v in enumerate(soh) if v < soh_min]
            if r.is_compromised and below:
                assert r.first_breach_year == below[0] + 1
                # El año reportado está dentro del horizonte.
                assert 1 <= r.first_breach_year <= n
            if not r.is_compromised:
                assert r.first_breach_year is None

    def test_subrecomendaciones_invariantes(self):
        """Nivel y posición coherentes; mensaje vacío sólo en óptimo."""
        evaluators = {
            "discount_rate": (evaluate_discount_rate, "discount_rate"),
            "opex": (evaluate_opex, "opex_per_mw_year"),
            "rte": (evaluate_rte, "rte"),
            "lifespan": (evaluate_lifespan, "lifespan_years"),
            "retribution_price": (evaluate_retribution_price, "avg_spread_price"),
        }
        for _, (fn, range_key) in evaluators.items():
            for v in _grid(range_key, 40):
                s = fn(float(v))
                assert s.level in SUB_LEVELS
                assert s.position in SUB_POSITIONS
                # Correspondencia normativa nivel ↔ posición.
                assert LEVEL_TO_POSITION[s.level] == s.position
                # Mensaje vacío si y solo si está en óptimo.
                assert (s.message == "") == (s.position == "optimal")

    def test_mensaje_compuesto_invariantes_en_universo(self):
        """El narrador produce prosa válida para todo el universo muestreado."""
        rng = np.random.default_rng(7)
        rois = np.linspace(-0.3, 0.6, 8)
        discounts = _grid("discount_rate", 4)
        opexs = _grid("opex_per_mw_year", 4)
        rtes = _grid("rte", 4)
        for roi, i, opex, rte in itertools.product(rois, discounts, opexs, rtes):
            soh = list(np.clip(1.0 - 0.03 * np.arange(int(rng.integers(2, 16))), 0.4, 1.0))
            roi_r = evaluate_roi(float(roi), float(i))
            deg_r = evaluate_degradation(1.0 - soh[-1], 0.75, soh_end_by_year=soh)
            subs = [
                evaluate_discount_rate(float(i)),
                evaluate_opex(float(opex)),
                evaluate_rte(float(rte)),
            ]
            alarm = "Aviso de prueba" if rng.random() < 0.5 else ""
            msg = _compose_message(alarm, roi_r, deg_r, subs)
            # Invariantes de redacción.
            assert msg
            assert msg[0].isupper()
            assert msg.endswith(".")
            assert " + " not in msg
            assert "no recomendado" not in msg.lower()
            # Doble espacio: no debe haber (frases unidas con un único espacio).
            assert "  " not in msg

    def test_overall_color_prioridad(self):
        """blue > yellow > green en la resolución del color global."""
        inputs = SimulationInputs()
        # Caso azul: SoH comprometido fuerza azul aunque ROI sea verde.
        res_blue = _make_results(0.30, [0.90, 0.70])  # cruza 0.75
        assert generate_full_recommendation(inputs, res_blue).overall_color == "blue"
        # Caso verde: ROI holgado y SoH con margen.
        res_green = _make_results(0.30, [1.0, 0.99, 0.98])
        assert generate_full_recommendation(inputs, res_green).overall_color == "green"
