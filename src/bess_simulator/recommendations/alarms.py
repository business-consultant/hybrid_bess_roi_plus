"""Registro de eventos críticos (APM).

Detecta y registra los episodios en los que magnitudes **críticas** del activo
—por seguridad, salud o garantía contractual— han operado fuera de los rangos
admisibles. El objetivo es dejar traza histórica de esos eventos para el panel
de Asset Performance Management.

Magnitudes vigiladas (mapeadas a columnas del dataset histórico):
  - **Temperatura** (°C) → SEGURIDAD: sobre-temperatura del sistema (riesgo
    térmico). Umbral ``alarm_temp_critical_c``.
  - **RTE** (round-trip efficiency) → GARANTÍA: rendimiento por debajo del
    mínimo contractual. Umbral ``alarm_rte_min``.
  - **SoH** (state of health) → SALUD/GARANTÍA: capacidad por debajo del mínimo
    garantizado. Umbral ``alarm_soh_min``.

Cada :class:`Alarm` lleva un campo ``subelement`` con el subsistema responsable,
pensado para que más adelante una notificación enlace (atajo) con la pantalla de
detalle por elemento.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# --- Categorías de criticidad ---
CATEGORY_SAFETY = "Seguridad"
CATEGORY_HEALTH = "Salud del activo"
CATEGORY_WARRANTY = "Garantía contractual"

# --- Severidad ---
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"

ALARM_PARAMS = ["C-RATE", "RTE", "DoD", "SoC", "Temperatura"]


@dataclass
class Alarm:
    """Evento histórico de una magnitud crítica fuera de rango."""

    parameter: str
    message: str
    category: str = ""
    severity: str = SEVERITY_WARNING
    count: int = 0
    first_timestamp: pd.Timestamp | None = None
    last_timestamp: pd.Timestamp | None = None
    threshold: float | None = None
    worst_value: float | None = None
    # Subsistema responsable; referencia para el atajo a la pantalla de
    # elementos (a implementar en la Fase 7).
    subelement: str = ""


def _event_extent(mask: pd.Series, timestamps: pd.Series | None):
    """Devuelve (recuento, primer ts, último ts) de los intervalos marcados."""
    count = int(mask.sum())
    if count == 0 or timestamps is None:
        return count, None, None
    selected = timestamps[mask]
    return count, selected.min(), selected.max()


def check_historical_alarms(
    interval_data: pd.DataFrame,
    rte_range: tuple[float, float] = (0.80, 0.90),
    cfg: dict | None = None,
) -> list[Alarm]:
    """Detecta eventos críticos en el histórico (seguridad/salud/garantía).

    Escanea las columnas disponibles en ``interval_data``. Si una columna no
    está presente, simplemente se omite esa comprobación (compatibilidad con
    datasets parciales como el del motor de simulación, que solo aporta RTE).
    """
    if interval_data is None or interval_data.empty:
        return []

    # Umbrales (configurables); valores por defecto seguros si no hay cfg.
    cfg = cfg or {}
    temp_critical = cfg.get("alarm_temp_critical_c", 40.0)
    rte_min = cfg.get("alarm_rte_min", rte_range[0])
    soh_min = cfg.get("alarm_soh_min", 0.80)

    timestamps = interval_data["timestamp"] if "timestamp" in interval_data else None
    alarms: list[Alarm] = []

    # --- Temperatura alta → SEGURIDAD ---
    if "temperature" in interval_data.columns:
        mask = interval_data["temperature"] > temp_critical
        count, first_ts, last_ts = _event_extent(mask, timestamps)
        if count > 0:
            worst = float(interval_data.loc[mask, "temperature"].max())
            alarms.append(Alarm(
                parameter="Temperatura",
                message=(
                    f"Sobre-temperatura por encima de {temp_critical:.0f} °C en "
                    f"{count:,} intervalos (pico {worst:.1f} °C)"
                ),
                category=CATEGORY_SAFETY,
                severity=SEVERITY_CRITICAL,
                count=count,
                first_timestamp=first_ts,
                last_timestamp=last_ts,
                threshold=temp_critical,
                worst_value=worst,
                subelement="Sistema térmico / HVAC",
            ))

    # --- RTE bajo → GARANTÍA contractual de rendimiento ---
    if "rte" in interval_data.columns:
        mask = interval_data["rte"] < rte_min
        count, first_ts, last_ts = _event_extent(mask, timestamps)
        if count > 0:
            worst = float(interval_data.loc[mask, "rte"].min())
            alarms.append(Alarm(
                parameter="RTE",
                message=(
                    f"Rendimiento de ciclo por debajo del mínimo contractual "
                    f"({rte_min:.0%}) en {count:,} intervalos (mínimo {worst:.1%})"
                ),
                category=CATEGORY_WARRANTY,
                severity=SEVERITY_WARNING,
                count=count,
                first_timestamp=first_ts,
                last_timestamp=last_ts,
                threshold=rte_min,
                worst_value=worst,
                subelement="PCS / Inversor BESS",
            ))

    # --- SoH bajo garantizado → SALUD / GARANTÍA ---
    if "soh" in interval_data.columns:
        mask = interval_data["soh"] < soh_min
        count, first_ts, last_ts = _event_extent(mask, timestamps)
        if count > 0:
            worst = float(interval_data.loc[mask, "soh"].min())
            alarms.append(Alarm(
                parameter="SoH",
                message=(
                    f"Estado de salud por debajo del mínimo garantizado "
                    f"({soh_min:.0%}) en {count:,} intervalos (mínimo {worst:.1%})"
                ),
                category=CATEGORY_HEALTH,
                severity=SEVERITY_CRITICAL,
                count=count,
                first_timestamp=first_ts,
                last_timestamp=last_ts,
                threshold=soh_min,
                worst_value=worst,
                subelement="Módulos BESS",
            ))

    return alarms


def generate_alarm_message(alarms: list[Alarm]) -> str:
    """Resumen en lenguaje natural de los parámetros con eventos registrados."""
    if not alarms:
        return ""
    params = ", ".join(a.parameter for a in alarms)
    return (
        "El sistema BESS ha operado puntualmente fuera de los rangos aconsejados "
        f"en términos de {params}."
    )
