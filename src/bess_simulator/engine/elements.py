"""Síntesis de indicadores por subelemento para la vista de monitorización (Fase 7).

APM es una herramienta de **análisis** (resolución 15 min, en el futuro 5 min),
no de tiempo real: por eso las tablas resumen **variables agregadas sobre el
periodo seleccionado** (máximos, medias, disponibilidad), una fila por unidad.

  - :func:`build_bess_snapshot`: una fila por módulo/rack de batería con SoC,
    SoH, DoD máx., temperatura máx. de celda, desviación máx. de tensión entre
    celdas e intensidad máx. del periodo.
  - :func:`build_pcs_snapshot`: una fila por convertidor (PCS) con PR del
    inversor, producción y disponibilidad del periodo.
  - :func:`build_panel_data`: magnitudes agregadas del panel "BESS Data".

Es síntesis de visualización del prototipo: los valores por unidad se derivan
de los agregados del histórico con una dispersión realista entre unidades, de
modo que sean coherentes con los KPIs de planta y reproducibles (semilla
estable). No representan telemetría real.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bess_simulator.config import INTERVAL_DURATION_H
from bess_simulator.models.results import PlantSummary

# Estados posibles de una unidad y su representación visual.
STATUS_AVAILABLE = "disponible"
STATUS_WARNING = "aviso"
STATUS_FAULT = "fallo"

STATUS_ICON = {
    STATUS_AVAILABLE: "🟢",
    STATUS_WARNING: "🟡",
    STATUS_FAULT: "🔴",
}
STATUS_LABEL = {
    STATUS_AVAILABLE: "Disponible",
    STATUS_WARNING: "Aviso",
    STATUS_FAULT: "Fallo",
}

# Umbrales de garantía (warranty compliance) para el semáforo de la cabecera
# del detalle BESS. Son los límites contractuales típicos sobre el peor módulo
# y sobre la dispersión del grupo; pueden sobrescribirse desde Configuración.
DEFAULT_WARRANTY_THRESHOLDS = {
    "soh_min": 80.0,        # SoH mínimo garantizado (%) — suelo contractual
    "soh_warn_margin": 2.0,  # margen de aviso por encima del suelo (pp)
    "soh_spread_max": 5.0,   # dispersión máx. de SoH admisible en el grupo (pp)
    "cell_temp_max": 40.0,   # temperatura máx. de celda admisible (°C)
    "cycles_max": 6000.0,    # tope contractual de ciclos equivalentes
    "dod_max": 100.0,        # DoD máx. admisible por ciclo (%)
}


def _last_historical_row(df: pd.DataFrame | None) -> pd.Series | None:
    """Última fila del histórico (is_forecast == False); si no, la última."""
    if df is None or df.empty:
        return None
    if "is_forecast" in df.columns:
        hist = df[~df["is_forecast"]]
        if not hist.empty:
            return hist.iloc[-1]
    return df.iloc[-1]


def _historical(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Subconjunto histórico del dataset (is_forecast == False); si no, todo."""
    if df is None or df.empty:
        return None
    if "is_forecast" in df.columns:
        hist = df[~df["is_forecast"]]
        if not hist.empty:
            return hist
    return df


def _hierarchical_names(prefix: str, n: int, sep: str, levels: list[int]) -> list[str]:
    """Genera ``n`` nombres jerárquicos tipo ``BESS.1.A.1.1`` / ``PCS_1.A.1``.

    ``levels`` define el tamaño de los niveles numéricos intermedios; el nivel
    de array se nombra con letras (A, B, C, ...). El último nivel es el índice
    de unidad dentro del grupo.
    """
    names: list[str] = []
    array_idx = 0
    group_idx = 1
    unit_idx = 1
    units_per_group = levels[-1]
    groups_per_array = levels[0] if len(levels) > 1 else 1
    for _ in range(n):
        array_letter = chr(ord("A") + array_idx)
        if len(levels) > 1:
            names.append(f"{prefix}{sep}1.{array_letter}.{group_idx}.{unit_idx}")
        else:
            names.append(f"{prefix}{sep}1.{array_letter}.{unit_idx}")
        unit_idx += 1
        if unit_idx > units_per_group:
            unit_idx = 1
            group_idx += 1
            if group_idx > groups_per_array:
                group_idx = 1
                array_idx += 1
    return names


def _rng_for(summary: PlantSummary, df: pd.DataFrame | None, salt: int) -> np.random.Generator:
    """RNG estable: misma planta + mismo histórico ⇒ mismo snapshot."""
    base = int(round(summary.bess_capacity_mwh * 10)) + int(round(summary.nominal_power_mw))
    n = 0 if df is None else len(df)
    return np.random.default_rng(base + n + salt)


def _battery_glyph(soc: float, segments: int = 5) -> str:
    """Representación visual del estado de carga: pila + barra de segmentos."""
    level = float(np.clip(soc, 0.0, 100.0))
    filled = int(round(level / 100.0 * segments))
    icon = "🔋" if level >= 20.0 else "🪫"
    return f"{icon} " + "▰" * filled + "▱" * (segments - filled)


def build_panel_data(summary: PlantSummary, df: pd.DataFrame | None) -> dict:
    """Magnitudes agregadas del panel lateral 'BESS Data'."""
    rng = _rng_for(summary, df, salt=11)
    active_mw = float(summary.charge_discharge_avg_power_mw)
    # Reactiva y factor de potencia plausibles para un inversor bien ajustado.
    power_factor = float(np.clip(0.99 - rng.uniform(0.0, 0.02), 0.95, 1.0))
    reactive_mvar = abs(active_mw) * float(np.tan(np.arccos(power_factor)))
    # Factor de capacidad de la planta = energía exportada a red / (potencia de
    # evacuación × horas reales del periodo). Definición estándar (CF = E /
    # (P_n · T), Wikipedia/EIA). Se usa la potencia del punto de conexión (POI)
    # como referencia de "nameplate" de evacuación; si no está, la nominal del
    # BESS. Valores típicos PV/híbrido en España: ~20-30 %.
    capacity_factor = 0.0
    period_hours = (len(df) * INTERVAL_DURATION_H) if df is not None else 0.0
    ref_power_mw = summary.poi_limit_mw or summary.nominal_power_mw
    if ref_power_mw > 0 and period_hours > 0:
        exported_mwh = summary.exported_gwh * 1000.0
        capacity_factor = min(
            100.0, 100.0 * exported_mwh / (ref_power_mw * period_hours)
        )
    return {
        "active_power_mw": active_mw,
        "reactive_power_mvar": round(reactive_mvar, 1),
        "power_factor": round(power_factor, 2),
        "energy_exported_mwh": summary.exported_gwh * 1000.0,
        "energy_imported_mwh": summary.imported_gwh * 1000.0,
        "capacity_factor_pct": round(capacity_factor, 1),
    }


# Ganancia media de transposición plano-de-módulos / horizontal (GPOA/GHI) para
# un campo fijo inclinado ~latitud en España. El dataset base toma POA≈GHI; aquí
# se sintetiza una ganancia plausible para diferenciar ambas medidas.
PYRANOMETER_POA_GAIN = 1.10
# Sesgo de calibración entre sensores (±%) y ruido por muestra por sensor (±%).
PYRANOMETER_BIAS_PCT = 0.025
PYRANOMETER_NOISE_PCT = 0.012


def build_meteo_pyranometers(
    meteo: pd.DataFrame | None,
    n_sensors: int = 3,
    poa_gain: float = PYRANOMETER_POA_GAIN,
) -> pd.DataFrame:
    """Lecturas de varios piranómetros redundantes (GHI y GPOA).

    Simula ``n_sensors`` piranómetros físicos midiendo cada magnitud, con un
    sesgo de calibración fijo por sensor y un ruido por muestra pequeño (sensores
    redundantes en planta nunca coinciden exactamente). El GPOA (plano de
    módulos) se deriva del GHI con una ganancia de transposición ``poa_gain``.

    Conserva la **resolución nativa de la serie meteorológica** (15 min): el
    recurso solar es una magnitud fundamental y se muestrea con grano fino, no
    como media diaria. Devuelve un DataFrame con columnas ``timestamp``,
    ``ghi_clearsky``, ``ghi_p1..pN`` y ``gpoa_p1..pN``. Determinista.
    """
    cols = ["timestamp", "ghi_clearsky"]
    cols += [f"ghi_p{i + 1}" for i in range(n_sensors)]
    cols += [f"gpoa_p{i + 1}" for i in range(n_sensors)]
    if meteo is None or meteo.empty or "timestamp" not in meteo or "ghi" not in meteo:
        return pd.DataFrame(columns=cols)

    base = meteo.sort_values("timestamp").reset_index(drop=True)
    rng = np.random.default_rng(20240501 + len(base))
    ghi = base["ghi"].to_numpy()
    gpoa = ghi * float(poa_gain)

    out = pd.DataFrame({"timestamp": base["timestamp"]})
    out["ghi_clearsky"] = base["ghi_clearsky"] if "ghi_clearsky" in base else np.nan

    bias_ghi = 1.0 + rng.uniform(-PYRANOMETER_BIAS_PCT, PYRANOMETER_BIAS_PCT, n_sensors)
    bias_poa = 1.0 + rng.uniform(-PYRANOMETER_BIAS_PCT, PYRANOMETER_BIAS_PCT, n_sensors)
    for i in range(n_sensors):
        noise = rng.normal(1.0, PYRANOMETER_NOISE_PCT, len(ghi))
        out[f"ghi_p{i + 1}"] = np.clip(ghi * bias_ghi[i] * noise, 0.0, None)
    for i in range(n_sensors):
        noise = rng.normal(1.0, PYRANOMETER_NOISE_PCT, len(gpoa))
        out[f"gpoa_p{i + 1}"] = np.clip(gpoa * bias_poa[i] * noise, 0.0, None)
    return out


def build_bess_snapshot(
    summary: PlantSummary,
    df: pd.DataFrame | None,
    temp_critical_c: float = 40.0,
) -> pd.DataFrame:
    """Indicadores agregados del periodo por módulo de batería (BMS).

    Columnas vigiladas: carga (icono de pila), SoC, SoH, DoD máx., temperatura
    máx. de celda, desviación máx. de tensión entre celdas e intensidad máx.
    """
    n = max(1, int(summary.bess_modules))
    rng = _rng_for(summary, df, salt=1)
    hist = _historical(df)

    soh_base = (
        float(hist["soh"].iloc[-1]) if hist is not None and "soh" in hist
        else float(summary.state_of_health or 0.95)
    )
    temp_high = (
        float(hist["temperature"].quantile(0.95)) if hist is not None and "temperature" in hist
        else 30.0
    )
    soc_lo = float(summary.soc_min_pct) if summary.soc_min_pct else 15.0
    soc_hi = float(summary.soc_max_pct) if summary.soc_max_pct else 95.0
    unit_power_kw = (summary.nominal_power_mw * 1000.0) / n if n else 0.0

    soh = np.clip(soh_base * 100.0 + rng.normal(0.0, 0.8, n), 80.0, 100.0)
    # SoC medio representativo del periodo (centrado en la ventana operativa).
    soc_mid = (soc_lo + soc_hi) / 2.0
    soc = np.clip(soc_mid + rng.normal(0.0, 6.0, n), soc_lo - 5.0, soc_hi + 5.0)
    # DoD máx. alcanzado ≈ amplitud de la ventana de SoC, con dispersión.
    max_dod = np.clip((soc_hi - soc_lo) + rng.normal(0.0, 3.0, n), 0.0, 100.0)
    # Temperatura máx. de celda: temperatura alta de operación del contenedor +
    # calentamiento local del módulo (las celdas superan en unos grados la del
    # sistema). Solo una minoría de módulos se acerca al umbral crítico.
    temp_max_cell = temp_high + rng.uniform(2.0, 7.0, n) + rng.normal(0.0, 1.5, n)
    # Desviación máx. de tensión entre celdas: crece al degradarse el módulo.
    volt_dev_mv = np.clip(12.0 + (100.0 - soh) * 1.6 + rng.uniform(0.0, 6.0, n), 5.0, 80.0)
    # Intensidad máx.: corriente del módulo a tensión de pack nominal (~800 V).
    pack_voltage = 780.0 + 0.6 * soc
    current_max = unit_power_kw * 1000.0 / pack_voltage * rng.uniform(1.0, 1.2, n)
    # Ciclos equivalentes acumulados: en torno al total de planta con una
    # ligera dispersión entre módulos (estrés de ciclado para la garantía).
    cycles_base = float(summary.cycle_count or 0.0)
    cycles_equiv = np.clip(cycles_base * rng.uniform(0.94, 1.06, n), 0.0, None)

    temp_warn = temp_critical_c - 2.0
    status = np.where(
        (soh < 80.5) | (temp_max_cell > temp_critical_c + 2.0) | (volt_dev_mv > 55.0),
        STATUS_FAULT,
        np.where(
            (soh < 82.0) | (temp_max_cell > temp_warn) | (volt_dev_mv > 38.0),
            STATUS_WARNING, STATUS_AVAILABLE,
        ),
    )

    names = _hierarchical_names("BESS", n, sep=".", levels=[9, 3])
    soc_round = np.round(soc, 1)
    return pd.DataFrame({
        "Estado": [STATUS_ICON[s] for s in status],
        "Nombre": names,
        "Carga": [_battery_glyph(v) for v in soc_round],
        "SoC (%)": soc_round,
        "SoH (%)": np.round(soh, 1),
        "DoD máx. (%)": np.round(max_dod, 1),
        "Tª máx. celda (°C)": np.round(temp_max_cell, 1),
        "Desv. máx. tensión celda (mV)": np.round(volt_dev_mv, 1),
        "Intensidad máx. (A)": np.round(current_max, 1),
        "Ciclos equiv.": np.round(cycles_equiv, 0).astype(int),
        "_status": status,
    })


def _grade_high(value: float, limit: float, warn_band: float) -> str:
    """Semáforo para magnitudes donde *más alto es peor* (Tª, ciclos, DoD…)."""
    if value > limit:
        return STATUS_FAULT
    if value > limit - warn_band:
        return STATUS_WARNING
    return STATUS_AVAILABLE


def _grade_low(value: float, floor: float, warn_margin: float) -> str:
    """Semáforo para magnitudes donde *más bajo es peor* (SoH)."""
    if value < floor:
        return STATUS_FAULT
    if value < floor + warn_margin:
        return STATUS_WARNING
    return STATUS_AVAILABLE


def build_bess_warranty_kpis(
    snapshot: pd.DataFrame, thresholds: dict | None = None
) -> list[dict]:
    """KPIs de cabecera para *warranty compliance* del grupo de módulos BESS.

    Resume la salud y uniformidad de la flota de baterías (la garantía suele
    fijar umbrales sobre el peor módulo y sobre la dispersión del grupo):

      - SoH mínimo (módulo más degradado, frente al suelo de garantía);
      - SoH spread = máx − mín (variabilidad / desequilibrio del grupo);
      - módulo con mayor desviación de SoH respecto a la media;
      - módulo con mayor desviación de temperatura respecto a la media;
      - módulo con mayor intensidad máxima del periodo;
      - módulo con mayor desviación de tensión entre celdas (balanceo);
      - DoD máx. del grupo (estrés de ciclado);
      - temperatura de celda máxima absoluta del periodo;
      - ciclos equivalentes máximos acumulados.

    Cada tarjeta lleva un *semáforo de garantía* (``status``) contra los
    umbrales de ``thresholds`` (ver :data:`DEFAULT_WARRANTY_THRESHOLDS`):
    ``disponible``/``aviso``/``fallo`` para las magnitudes con límite
    contractual y ``None`` para las puramente informativas (dispersión).

    Devuelve una lista de tarjetas ``{title, value, element, status, limit}``
    lista para pintar en la cabecera del detalle.
    """
    if snapshot.empty:
        return []

    th = {**DEFAULT_WARRANTY_THRESHOLDS, **(thresholds or {})}
    soh_min = float(th["soh_min"])
    soh_warn = float(th["soh_warn_margin"])
    spread_max = float(th["soh_spread_max"])
    temp_max = float(th["cell_temp_max"])
    cycles_max = float(th["cycles_max"])
    dod_max = float(th["dod_max"])

    soh = snapshot["SoH (%)"]
    temp = snapshot["Tª máx. celda (°C)"]
    current = snapshot["Intensidad máx. (A)"]
    volt = snapshot["Desv. máx. tensión celda (mV)"]
    dod = snapshot["DoD máx. (%)"]
    cycles = snapshot["Ciclos equiv."]
    names = snapshot["Nombre"]

    soh_mean = float(soh.mean())
    temp_mean = float(temp.mean())
    soh_dev = (soh - soh_mean).abs()
    temp_dev = (temp - temp_mean).abs()

    i_soh_min = soh.idxmin()
    i_soh_dev = soh_dev.idxmax()
    i_temp_dev = temp_dev.idxmax()
    i_curr = current.idxmax()
    i_volt = volt.idxmax()
    i_dod = dod.idxmax()
    i_temp_max = temp.idxmax()
    i_cycles = cycles.idxmax()

    soh_min_val = float(soh.loc[i_soh_min])
    spread_val = float(soh.max() - soh.min())
    dod_val = float(dod.loc[i_dod])
    temp_max_val = float(temp.loc[i_temp_max])
    cycles_val = int(cycles.loc[i_cycles])

    return [
        {
            "title": "SoH mínimo",
            "value": f"{soh_min_val:.1f} %",
            "element": str(names.loc[i_soh_min]),
            "status": _grade_low(soh_min_val, soh_min, soh_warn),
            "limit": f"suelo {soh_min:.0f} %",
        },
        {
            "title": "SoH spread (grupo)",
            "value": f"{spread_val:.1f} pp",
            "element": f"mín {float(soh.min()):.1f} % · máx {float(soh.max()):.1f} %",
            "status": _grade_high(spread_val, spread_max, spread_max * 0.3),
            "limit": f"máx. {spread_max:.0f} pp",
        },
        {
            "title": "Desvío máx. SoH",
            "value": f"{float(soh_dev.loc[i_soh_dev]):.1f} pp",
            "element": str(names.loc[i_soh_dev]),
            "status": None,
            "limit": None,
        },
        {
            "title": "Desvío máx. Tª",
            "value": f"{float(temp_dev.loc[i_temp_dev]):.1f} °C",
            "element": str(names.loc[i_temp_dev]),
            "status": None,
            "limit": None,
        },
        {
            "title": "Intensidad máxima",
            "value": f"{float(current.loc[i_curr]):.0f} A",
            "element": str(names.loc[i_curr]),
            "status": None,
            "limit": None,
        },
        {
            "title": "Desv. máx. tensión celda",
            "value": f"{float(volt.loc[i_volt]):.0f} mV",
            "element": str(names.loc[i_volt]),
            "status": None,
            "limit": None,
        },
        {
            "title": "DoD máx. (grupo)",
            "value": f"{dod_val:.1f} %",
            "element": str(names.loc[i_dod]),
            "status": _grade_high(dod_val, dod_max, 1.0),
            "limit": f"máx. {dod_max:.0f} %",
        },
        {
            "title": "Tª máx. celda absoluta",
            "value": f"{temp_max_val:.1f} °C",
            "element": str(names.loc[i_temp_max]),
            "status": _grade_high(temp_max_val, temp_max, 2.0),
            "limit": f"máx. {temp_max:.0f} °C",
        },
        {
            "title": "Ciclos equiv. máx.",
            "value": f"{cycles_val:,}",
            "element": str(names.loc[i_cycles]),
            "status": _grade_high(cycles_val, cycles_max, cycles_max * 0.15),
            "limit": f"tope {cycles_max:,.0f}",
        },
    ]


def build_pcs_snapshot(summary: PlantSummary, df: pd.DataFrame | None) -> pd.DataFrame:
    """Indicadores agregados del periodo por convertidor (PCS).

    Columnas: PR del inversor, producción y disponibilidad del periodo.
    """
    n = max(1, int(summary.pcs))
    rng = _rng_for(summary, df, salt=2)
    hist = _historical(df)

    rte_base = (
        float(hist["rte"].mean()) if hist is not None and "rte" in hist
        else float(summary.roundtrip_efficiency or 0.88)
    )
    total_mwh = float(summary.exported_gwh) * 1000.0
    prod_per_unit = total_mwh / n if n else 0.0

    # PR (performance ratio) del inversor a partir del rendimiento round-trip.
    pr = np.clip(rte_base * 100.0 + rng.normal(0.0, 1.2, n), 70.0, 99.0)
    # Producción por inversor (reparto del total con dispersión entre unidades).
    production_mwh = np.clip(prod_per_unit * rng.uniform(0.90, 1.10, n), 0.0, None)
    # Disponibilidad temporal por inversor.
    availability = np.clip(
        float(summary.time_based_availability or 98.0) + rng.normal(0.0, 0.8, n),
        80.0, 100.0,
    )

    status = np.where(
        (availability < 90.0) | (pr < 78.0), STATUS_FAULT,
        np.where((availability < 95.0) | (pr < 82.0), STATUS_WARNING, STATUS_AVAILABLE),
    )

    names = _hierarchical_names("PCS", n, sep="_", levels=[7])
    return pd.DataFrame({
        "Estado": [STATUS_ICON[s] for s in status],
        "Nombre": names,
        "PR inversor (%)": np.round(pr, 1),
        "Producción (MWh)": np.round(production_mwh, 1),
        "Disponibilidad (%)": np.round(availability, 1),
        "_status": status,
    })


def build_pcs_power_series(summary: PlantSummary, bundle: dict | None) -> pd.DataFrame:
    """Serie diaria de **potencia específica** (p.u.) por inversor (PCS).

    La planta está acoplada en AC, así que el PCS es a la vez inversor del BESS
    y del campo PV. Para comparar inversores de forma homogénea se usa la
    *potencia específica* = potencia activa AC / potencia DC instalada (p.u.,
    MW/MWp), independiente del tamaño de cada unidad.

    Se deriva del perfil PV de referencia, normalizado por la potencia pico DC
    de la planta y repartido en ``summary.pcs`` inversores con una ligera
    dispersión de rendimiento entre unidades (suciedad, *mismatch*…). Devuelve
    un DataFrame con columna ``timestamp`` y una columna por inversor; vacío si
    no hay datos PV.
    """
    if bundle is None:
        return pd.DataFrame()
    pv = bundle.get("pv")
    n = max(1, int(summary.pcs))
    peak_dc_mwp = float(summary.pv_peak_mwp or 0.0)
    if pv is None or pv.empty or "timestamp" not in pv or "p_ac_mw" not in pv or peak_dc_mwp <= 0:
        return pd.DataFrame()

    daily = (
        pv[["timestamp", "p_ac_mw"]]
        .set_index("timestamp")
        .resample("D")
        .mean()
        .reset_index()
    )
    base_pu = np.clip(daily["p_ac_mw"].to_numpy() / peak_dc_mwp, 0.0, None)

    rng = _rng_for(summary, bundle.get("df"), salt=3)
    factors = rng.uniform(0.93, 1.03, n)  # rendimiento relativo de cada inversor
    names = _hierarchical_names("PCS", n, sep="_", levels=[7])

    out = pd.DataFrame({"timestamp": daily["timestamp"]})
    for name, factor in zip(names, factors):
        noise = rng.normal(0.0, 0.004, len(base_pu))
        out[name] = np.clip(base_pu * factor + noise, 0.0, None)
    return out


# ---------------------------------------------------------------------------
# HVAC — climatización de los contenedores (sistemas auxiliares)
# ---------------------------------------------------------------------------

# Parámetros por defecto de los sistemas auxiliares de climatización. Promedio
# de 1 HVAC + 1 sistema de supresión de incendios por contenedor. Valores de
# referencia de plantas utility-scale; ajustables desde Configuración.
DEFAULT_HVAC_PARAMS = {
    "container_mwh": 5.0,         # capacidad por contenedor (MWh) → nº de contenedores
    "cop_target": 3.0,           # COP objetivo (ideal > 3) en modo enfriamiento
    "delta_t_max": 5.0,          # uniformidad: ΔT máx. admisible en contenedor (°C)
    "availability_target": 98.0,  # disponibilidad objetivo (% uptime)
    "hvac_share_pct": 5.0,       # consumo HVAC como % del throughput del BESS
}


def n_containers(summary: PlantSummary, params: dict | None = None) -> int:
    """Nº de contenedores ≈ capacidad BESS / capacidad por contenedor.

    Se asume 1 HVAC + 1 sistema de supresión por contenedor.
    """
    p = {**DEFAULT_HVAC_PARAMS, **(params or {})}
    per = float(p.get("container_mwh") or 5.0) or 5.0
    cap = float(summary.bess_capacity_mwh or 0.0)
    return int(max(1, round(cap / per)))


def build_hvac_snapshot(
    summary: PlantSummary,
    df: pd.DataFrame | None,
    params: dict | None = None,
) -> pd.DataFrame:
    """Indicadores agregados del periodo por contenedor (climatización HVAC).

    Una fila por contenedor con:
      - **COP** (eficiencia de enfriamiento, capacidad/energía eléctrica);
      - **Uniformidad ΔT** = máx(Tᵢ) − mín(Tᵢ) de los sensores del contenedor;
      - **Consumo** del periodo (MWh) y su **% sobre el throughput del BESS**;
      - **Disponibilidad** (% uptime, incluye alertas de flujo de aire).
    """
    p = {**DEFAULT_HVAC_PARAMS, **(params or {})}
    n = n_containers(summary, p)
    rng = _rng_for(summary, df, salt=4)
    hist = _historical(df)

    # Temperatura ambiente representativa del periodo: cuanto más cálido, peor COP
    # y mayor consumo de enfriamiento.
    if hist is not None and "temperature" in hist:
        temp_amb = float(hist["temperature"].mean())
    else:
        temp_amb = 25.0
    cop_target = float(p["cop_target"])
    delta_t_max = float(p["delta_t_max"])
    avail_target = float(p["availability_target"])

    # COP: ~cop_target+0.6 en condiciones suaves (25 °C), degradándose con el calor.
    cop = np.clip(
        cop_target + 0.6 - 0.045 * (temp_amb - 25.0) + rng.normal(0.0, 0.18, n),
        2.0, 5.0,
    )
    # Uniformidad térmica: ΔT entre sensores del contenedor (grid ~9 puntos).
    delta_t = np.clip(
        2.4 + 0.05 * max(0.0, temp_amb - 25.0) + rng.gamma(2.0, 0.6, n),
        0.5, 9.5,
    )
    # Disponibilidad (uptime), con alertas de flujo de aire en una minoría. Se
    # centra ligeramente por encima del objetivo para que la media del grupo
    # ronde el objetivo (el recorte a 100 % sesgaría la media a la baja).
    availability = np.clip(avail_target + 0.7 + rng.normal(0.0, 1.0, n), 92.0, 100.0)

    # Consumo HVAC del periodo: parte del throughput del BESS (energía gestionada
    # por el PCS), repartido por contenedor con dispersión. El factor climático
    # eleva el consumo en periodos cálidos.
    throughput_mwh = (float(summary.exported_gwh) + float(summary.imported_gwh)) * 1000.0
    climate = 1.0 + 0.03 * (temp_amb - 25.0)
    hvac_total_mwh = max(0.0, throughput_mwh * (float(p["hvac_share_pct"]) / 100.0) * climate)
    per_unit = hvac_total_mwh / n if n else 0.0
    consumption_mwh = np.clip(per_unit * rng.uniform(0.85, 1.15, n), 0.0, None)
    bess_per_unit = throughput_mwh / n if n else 0.0
    pct_bess = np.where(bess_per_unit > 0, consumption_mwh / bess_per_unit * 100.0, 0.0)

    status = np.where(
        (cop < 2.5) | (delta_t > delta_t_max + 1.5) | (availability < 95.0),
        STATUS_FAULT,
        np.where(
            (cop < cop_target) | (delta_t > delta_t_max) | (availability < avail_target),
            STATUS_WARNING, STATUS_AVAILABLE,
        ),
    )

    names = [f"HVAC_{i + 1:02d}" for i in range(n)]
    return pd.DataFrame({
        "Estado": [STATUS_ICON[s] for s in status],
        "Contenedor": names,
        "COP": np.round(cop, 2),
        "Uniformidad ΔT (°C)": np.round(delta_t, 1),
        "Consumo (MWh)": np.round(consumption_mwh, 1),
        "Consumo (% BESS)": np.round(pct_bess, 2),
        "Disponibilidad (%)": np.round(availability, 1),
        "_status": status,
    })


def build_hvac_kpis(
    snapshot: pd.DataFrame,
    summary: PlantSummary,
    params: dict | None = None,
) -> list[dict]:
    """KPIs de cabecera del grupo HVAC (COP, uniformidad, consumo, disponibilidad).

    Devuelve tarjetas ``{title, value, element, status, limit}`` con semáforo
    contra los objetivos de ``params`` (ver :data:`DEFAULT_HVAC_PARAMS`).
    """
    if snapshot.empty:
        return []
    p = {**DEFAULT_HVAC_PARAMS, **(params or {})}
    cop_target = float(p["cop_target"])
    delta_t_max = float(p["delta_t_max"])
    avail_target = float(p["availability_target"])

    cop = snapshot["COP"]
    delta_t = snapshot["Uniformidad ΔT (°C)"]
    consumption = snapshot["Consumo (MWh)"]
    pct_bess = snapshot["Consumo (% BESS)"]
    avail = snapshot["Disponibilidad (%)"]
    names = snapshot["Contenedor"]

    cop_mean = float(cop.mean())
    i_cop_min = cop.idxmin()
    i_dt_max = delta_t.idxmax()
    i_avail_min = avail.idxmin()
    dt_worst = float(delta_t.loc[i_dt_max])
    avail_mean = float(avail.mean())
    total_mwh = float(consumption.sum())
    pct_mean = float(pct_bess.mean())

    return [
        {
            "title": "COP medio (enfriamiento)",
            "value": f"{cop_mean:.2f}",
            "element": f"peor {float(cop.loc[i_cop_min]):.2f} · {names.loc[i_cop_min]}",
            "status": _grade_low(cop_mean, cop_target, 0.3),
            "limit": f"ideal > {cop_target:.1f}",
            "help": (
                "Coeficiente de rendimiento (Coefficient of Performance): ratio "
                "entre el calor extraído del contenedor y la energía eléctrica "
                "consumida por el HVAC (COP = capacidad de enfriamiento / consumo "
                "eléctrico). Adimensional; cuanto más alto, más eficiente. Un valor "
                f"> {cop_target:.1f} se considera bueno en modo enfriamiento. Se "
                "muestra la media del grupo y el peor contenedor."
            ),
        },
        {
            "title": "Uniformidad de temperatura",
            "value": f"{dt_worst:.1f} °C",
            "element": f"peor contenedor · {names.loc[i_dt_max]}",
            "status": _grade_high(dt_worst, delta_t_max, 1.0),
            "limit": f"ΔT máx. < {delta_t_max:.0f} °C",
            "help": (
                "Uniformidad de temperatura dentro del contenedor: diferencia "
                "entre el sensor más caliente y el más frío del grid de sensores "
                "(ΔT = máx(Tᵢ) − mín(Tᵢ)). Una ΔT baja indica un reparto homogéneo "
                "del aire frío; valores altos delatan puntos calientes que aceleran "
                f"el envejecimiento de las celdas. Umbral de alarma: ΔT > "
                f"{delta_t_max:.0f} °C. Se muestra el peor contenedor del grupo."
            ),
        },
        {
            "title": "Consumo energético HVAC",
            "value": f"{total_mwh:,.1f} MWh",
            "element": f"{pct_mean:.2f} % del total BESS",
            "status": None,
            "limit": None,
            "help": (
                "Energía eléctrica consumida por la climatización durante el "
                "periodo seleccionado (∫ P_HVAC · dt), sumada para todos los "
                "contenedores, y su peso relativo sobre la energía total "
                "gestionada por el BESS (cargada + descargada). Es un consumo "
                "auxiliar (parásito) que reduce la eficiencia global de la planta; "
                "monitorizarlo ayuda a optimizar la operación."
            ),
        },
        {
            "title": "Disponibilidad HVAC",
            "value": f"{avail_mean:.1f} %",
            "element": f"peor {float(avail.loc[i_avail_min]):.1f} % · {names.loc[i_avail_min]}",
            "status": _grade_low(avail_mean, avail_target, 1.0),
            "limit": f"objetivo > {avail_target:.0f} %",
            "help": (
                "Porcentaje de tiempo en que el HVAC estuvo operativo sin fallos "
                "(disponibilidad = tiempo activo / tiempo total × 100). El tiempo "
                "activo descuenta paradas por avería y alertas de flujo de aire "
                "(p. ej. obstrucción de filtros, detectada por presión "
                f"diferencial). Objetivo de servicio: > {avail_target:.0f} %. Se "
                "muestra la media del grupo y el peor contenedor."
            ),
        },
    ]


def build_hvac_consumption_series(
    summary: PlantSummary,
    bundle: dict | None,
    params: dict | None = None,
) -> pd.DataFrame:
    """Tendencia diaria del consumo HVAC (MWh) y su % sobre el throughput BESS.

    El consumo de climatización se modela como una fracción del throughput del
    BESS modulada por la temperatura ambiente diaria (más calor ⇒ más
    enfriamiento). Columnas: ``timestamp``, ``consumo_mwh``, ``pct_bess``.
    """
    if bundle is None:
        return pd.DataFrame(columns=["timestamp", "consumo_mwh", "pct_bess"])
    p = {**DEFAULT_HVAC_PARAMS, **(params or {})}
    df = bundle.get("df")
    if df is None or df.empty or "timestamp" not in df or "temperature" not in df.columns:
        return pd.DataFrame(columns=["timestamp", "consumo_mwh", "pct_bess"])

    hist = _historical(df)
    daily = (
        hist[["timestamp", "temperature"]]
        .set_index("timestamp")
        .resample("D")
        .mean()
        .reset_index()
    )
    if daily.empty:
        return pd.DataFrame(columns=["timestamp", "consumo_mwh", "pct_bess"])

    n_days = max(1, len(daily))
    throughput_mwh = (float(summary.exported_gwh) + float(summary.imported_gwh)) * 1000.0
    share = float(p["hvac_share_pct"]) / 100.0
    temp = daily["temperature"].to_numpy()
    temp_mean = float(np.nanmean(temp)) if len(temp) else 25.0
    climate = 1.0 + 0.03 * (temp - temp_mean)

    bess_per_day = throughput_mwh / n_days
    consumo = np.clip(bess_per_day * share * climate, 0.0, None)
    pct = np.where(bess_per_day > 0, consumo / bess_per_day * 100.0, 0.0)

    return pd.DataFrame({
        "timestamp": daily["timestamp"],
        "consumo_mwh": np.round(consumo, 2),
        "pct_bess": np.round(pct, 2),
    })


def status_counts(snapshot: pd.DataFrame) -> dict:
    """Recuento de unidades por estado a partir de la columna ``_status``."""
    col = snapshot["_status"] if "_status" in snapshot.columns else pd.Series(dtype=object)
    return {
        STATUS_AVAILABLE: int((col == STATUS_AVAILABLE).sum()),
        STATUS_WARNING: int((col == STATUS_WARNING).sum()),
        STATUS_FAULT: int((col == STATUS_FAULT).sum()),
    }
