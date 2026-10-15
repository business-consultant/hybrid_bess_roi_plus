"""Catálogo y generación bajo demanda de telemetría BESS para tendencias.

Las señales proceden exclusivamente de ``Prompts_Señales_BESS_bessplant``.
Se calculan a partir del dataset operativo de 15 minutos del prototipo; el
generador SCADA externo conserva el requisito de persistencia a un minuto.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SignalDefinition:
    name: str
    unit: str
    aggregation: str
    description: str


SIGNAL_CATALOG: dict[str, tuple[SignalDefinition, ...]] = {
    "Operación BESS": (
        SignalDefinition("income", "EUR", "SUM", "Ingreso de arbitraje por intervalo."),
        SignalDefinition("capture_price", "EUR/MWh", "AVG-1M", "Precio de captura de mercado."),
        SignalDefinition("average_market_price", "EUR/MWh", "AVG-1M", "Precio medio de mercado."),
        SignalDefinition("energy_sold_mwh", "MWh", "SUM", "Energía vendida por intervalo."),
        SignalDefinition("soh", "%", "LAST-1M", "Estado de salud BESS."),
        SignalDefinition("cycles", "FEC", "SUM", "Ciclos equivalentes por intervalo."),
        SignalDefinition("temperature", "°C", "AVG-1M", "Temperatura operativa BESS."),
        SignalDefinition("rte", "%", "AVG-1M", "Rendimiento round-trip."),
    ),
    "Estación meteorológica": (
        SignalDefinition("solar_elevation", "grados", "AVG-1M", "Elevación solar."),
        SignalDefinition("ghi", "W/m²", "AVG-1M", "Irradiancia global horizontal."),
        SignalDefinition("ghi_clearsky", "W/m²", "AVG-1M", "Irradiancia de cielo claro."),
        SignalDefinition("clearness_index", "", "AVG-1M", "Índice de claridad atmosférica."),
        SignalDefinition("temp_ambient", "°C", "AVG-1M", "Temperatura ambiente."),
        SignalDefinition("wind_speed", "m/s", "AVG-1M", "Velocidad de viento."),
        SignalDefinition("humidity", "%", "AVG-1M", "Humedad relativa ambiente."),
    ),
    "Planta FV": (
        SignalDefinition("poa", "W/m²", "AVG-1M", "Irradiancia efectiva en plano de generador."),
        SignalDefinition("temp_cell", "°C", "AVG-1M", "Temperatura de célula FV."),
        SignalDefinition("p_dc_mw", "MW", "AVG-1M", "Potencia FV DC previa al inversor."),
        SignalDefinition("p_ac_mw", "MW", "AVG-1M", "Potencia FV AC posterior a clipping."),
        SignalDefinition("p_clipped_mw", "MW", "AVG-1M", "Potencia FV recortada por inversor."),
    ),
    "BMS": (
        SignalDefinition("SystemStatus", "estado", "ESTADO-1M", "Estado del sistema de baterías."),
        SignalDefinition("SOC", "%", "LAST-1M", "Estado de carga del rack."),
        SignalDefinition("SOH", "%", "LAST-1M", "Estado de salud del rack."),
        SignalDefinition("DCCurrent", "A", "AVG-1M", "Corriente del bus DC."),
        SignalDefinition("DCVoltage", "V", "AVG-1M", "Tensión del bus DC."),
        SignalDefinition("DCPower", "kW", "AVG-1M", "Potencia DC del rack."),
        SignalDefinition("MaxCellTemp", "°C", "MAX-1M", "Máxima temperatura de celda."),
        SignalDefinition("MinCellTemp", "°C", "MIN-1M", "Mínima temperatura de celda."),
        SignalDefinition("AvgCellTemp", "°C", "AVG-1M", "Temperatura media de celda."),
        SignalDefinition("MaxCellVolt", "V", "MAX-1M", "Máxima tensión de celda."),
        SignalDefinition("MinCellVolt", "V", "MIN-1M", "Mínima tensión de celda."),
        SignalDefinition("AvgCellVolt", "V", "AVG-1M", "Tensión media de celda."),
        SignalDefinition("DCPowerChargeLim", "kW", "LAST-1M", "Límite de carga DC."),
        SignalDefinition("DCPowerDischargeLim", "kW", "LAST-1M", "Límite de descarga DC."),
        SignalDefinition("DCCurrentChargeLim", "A", "LAST-1M", "Límite de corriente de carga."),
        SignalDefinition("DCCurrentDischargeLim", "A", "LAST-1M", "Límite de corriente de descarga."),
    ),
    "BBANK": (
        SignalDefinition("TemperatureSensorXX", "°C", "AVG-1M", "Sensor de temperatura del contenedor."),
        SignalDefinition("MaxTemp", "°C", "MAX-1M", "Máxima temperatura del banco."),
        SignalDefinition("MaxTempAlarm", "booleano", "EVENTO-1M", "Alarma de máxima temperatura."),
        SignalDefinition("BTMSAlarm", "booleano", "EVENTO-1M", "Alarma del sistema térmico."),
        SignalDefinition("MFFPAlarm", "booleano", "EVENTO-1M", "Alarma contra incendios del banco."),
        SignalDefinition("FStop", "booleano", "EVENTO-1M", "Parada de emergencia."),
    ),
    "PCS": (
        SignalDefinition("ActivePower", "kW", "AVG-1M", "Potencia activa AC."),
        SignalDefinition("ReactivePower", "kvar", "AVG-1M", "Potencia reactiva AC."),
        SignalDefinition("CosPhi", "", "AVG-1M", "Factor de potencia."),
        SignalDefinition("Frequency", "Hz", "AVG-1M", "Frecuencia de red."),
        SignalDefinition("DCVoltage", "V", "AVG-1M", "Tensión DC en el PCS."),
        SignalDefinition("DCPower", "kW", "AVG-1M", "Potencia DC en el PCS."),
        SignalDefinition("DCCurrent", "A", "AVG-1M", "Corriente DC en el PCS."),
        SignalDefinition("InverterState", "estado", "ESTADO-1M", "Estado del inversor."),
        SignalDefinition("TotalEnergy", "kWh", "LAST-1M + Δ", "Contador acumulado exportado."),
        SignalDefinition("TotalImportedEnergy", "kWh", "LAST-1M + Δ", "Contador acumulado importado."),
        SignalDefinition("InverterAvailability", "%", "DERIVADA", "Disponibilidad calculada."),
        SignalDefinition("Performance", "%", "DERIVADA", "Rendimiento de conversión."),
        SignalDefinition("SOC", "%", "LAST-1M", "Réplica del SOC del banco."),
    ),
    "BCTRL": (
        SignalDefinition("ActivePower", "kW", "AVG-1M", "Suma de potencia activa de PCS."),
        SignalDefinition("ReactivePower", "kvar", "AVG-1M", "Suma de potencia reactiva de PCS."),
        SignalDefinition("Setpoint_ActivePower", "kW", "LAST-1M", "Consigna activa del banco."),
        SignalDefinition("Setpoint_ReactivePower", "kvar", "LAST-1M", "Consigna reactiva del banco."),
        SignalDefinition("SOC", "%", "LAST-1M", "SOC ponderado del banco."),
    ),
    "BTMS / HVAC": (
        SignalDefinition("Temperature", "°C", "AVG-1M", "Temperatura de climatización."),
        SignalDefinition("Humidity", "%", "AVG-1M", "Humedad relativa del recinto."),
        SignalDefinition("Pressure", "Pa", "AVG-1M", "Presión de conductos."),
        SignalDefinition("AirFlow", "m³/h", "AVG-1M", "Caudal de aire."),
        SignalDefinition("PowerConsumption", "kW", "AVG-1M", "Consumo del HVAC."),
        SignalDefinition("ComponentStatus", "estado", "ESTADO-1M", "Estado de ventiladores y bombas."),
        SignalDefinition("ControlSignal_Temp", "°C", "LAST-1M", "Consigna térmica."),
    ),
    "FPS / SCI": (
        SignalDefinition("SystemStatus", "estado", "ESTADO-1M", "Estado del sistema contra incendios."),
        SignalDefinition("SmokeSensorState", "booleano", "EVENTO-1M", "Detección de humo."),
        SignalDefinition("FireAlarm", "booleano", "EVENTO-1M", "Alarma de incendio."),
        SignalDefinition("ExtinctionDischarge", "booleano", "EVENTO-1M", "Descarga de agente extintor."),
        SignalDefinition("MFFPAlarm", "booleano", "EVENTO-1M", "Réplica de alarma de incendio."),
    ),
    "UPS": (SignalDefinition("SystemStatus", "estado", "ESTADO-1M", "Estado de alimentación ininterrumpida."),),
    "CT / Power Station": (SignalDefinition("SystemStatus", "estado", "ESTADO-1M", "Estado del centro de transformación."),),
    "ANL / MTR": (
        SignalDefinition("POI_ActivePower", "kW", "AVG-1M", "Potencia activa en el POI."),
        SignalDefinition("POI_ReactivePower", "kvar", "AVG-1M", "Potencia reactiva en el POI."),
    ),
    "EMS / PPC": (
        SignalDefinition("ControlMode", "estado", "ESTADO-1M", "Modo de control de planta."),
        SignalDefinition("Setpoint_ActivePower", "kW", "LAST-1M", "Consigna global activa."),
        SignalDefinition("Setpoint_ReactivePower", "kvar", "LAST-1M", "Consigna global reactiva."),
        SignalDefinition("ChargeLimitFromGrid", "kW", "LAST-1M", "Límite de carga desde red."),
        SignalDefinition("DischargeLimitToGrid", "kW", "LAST-1M", "Límite de descarga a red."),
    ),
}


def signal_definition(element: str, signal: str) -> SignalDefinition:
    for definition in SIGNAL_CATALOG[element]:
        if definition.name == signal:
            return definition
    raise KeyError(f"Señal no soportada: {element}/{signal}")


def build_signal_series(bundle: dict, element: str, signal: str) -> pd.DataFrame:
    """Construye una serie coherente de una señal del catálogo para tendencias."""
    definition = signal_definition(element, signal)
    existing_layers = {
        "Operación BESS": "df",
        "Estación meteorológica": "meteo",
        "Planta FV": "pv",
    }
    if element in existing_layers:
        source = bundle.get(existing_layers[element])
        if source is None or source.empty or signal not in source:
            return pd.DataFrame(columns=["timestamp", "value", "unit"])
        values = source[["timestamp", signal]].rename(columns={signal: "value"}).copy()
        if definition.unit == "%" and signal in {"soh", "rte", "humidity"}:
            values["value"] = values["value"] * 100.0
        return values.assign(unit=definition.unit)

    source = bundle.get("df")
    if source is None or source.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    frame = source[["timestamp", "energy_sold_mwh", "temperature", "soh"]].copy()
    timestamp = pd.to_datetime(frame["timestamp"])
    hours = timestamp.dt.hour.to_numpy() + timestamp.dt.minute.to_numpy() / 60.0
    n = len(frame)
    rated_kw = float(bundle.get("params", {}).get("rated_power_mw", 50.0)) * 1000.0
    discharge = np.clip(frame["energy_sold_mwh"].to_numpy(dtype=float) * 4000.0, 0.0, rated_kw)
    charging = np.where((hours >= 11.0) & (hours < 16.0), -rated_kw * 0.55, 0.0)
    active_kw = np.where(discharge > 1.0, discharge, charging)
    soc = np.clip(50.0 - 38.0 * np.sin(2.0 * np.pi * (hours - 7.0) / 24.0), 5.0, 95.0)
    soh = np.clip(frame["soh"].to_numpy(dtype=float) * 100.0, 70.0, 100.0)
    ambient = frame["temperature"].to_numpy(dtype=float)
    thermal_load = np.abs(active_kw) / max(rated_kw, 1.0)
    cell_temp = ambient + 2.0 + 7.0 * thermal_load
    dc_voltage = 1120.0 + 2.6 * soc - 0.018 * active_kw
    dc_power = active_kw / 0.97
    dc_current = dc_power * 1000.0 / np.maximum(dc_voltage, 1.0)
    perf = 96.0 + 1.5 * np.exp(-((thermal_load - 0.65) / 0.35) ** 2)
    reactive = np.sign(active_kw) * np.minimum(rated_kw * 0.35, np.abs(active_kw) * 0.25)
    cos_phi = active_kw / np.maximum(np.sqrt(active_kw ** 2 + reactive ** 2), 1.0)
    charge_lim = rated_kw * np.clip((100.0 - soc) / 18.0, 0.15, 1.0)
    discharge_lim = rated_kw * np.clip(soc / 18.0, 0.15, 1.0)
    airflow = 2200.0 + 3600.0 * thermal_load
    hvac_temp = 22.0 + 1.5 * np.sin(2.0 * np.pi * (hours - 14.0) / 24.0) + 1.5 * thermal_load
    btm_alarm = (cell_temp > 47.0).astype(int)
    fire_alarm = np.zeros(n, dtype=int)
    fstop = fire_alarm.copy()
    inverter_state = np.where(np.abs(active_kw) > 10.0, "Running", "Standby")
    bms_state = np.where(active_kw > 10.0, "Discharging", np.where(active_kw < -10.0, "Charging", "Standby"))
    exported = np.cumsum(np.maximum(active_kw, 0.0) * 0.25)
    imported = np.cumsum(np.maximum(-active_kw, 0.0) * 0.25)

    values: dict[str, object] = {
        "SystemStatus": bms_state,
        "SOC": soc,
        "SOH": soh,
        "DCCurrent": dc_current,
        "DCVoltage": dc_voltage,
        "DCPower": dc_power,
        "MaxCellTemp": cell_temp + 1.8,
        "MinCellTemp": cell_temp - 1.8,
        "AvgCellTemp": cell_temp,
        "MaxCellVolt": 3.05 + 0.006 * soc + 0.025 * (100.0 - soh) / 30.0,
        "MinCellVolt": 3.05 + 0.006 * soc - 0.025 * (100.0 - soh) / 30.0,
        "AvgCellVolt": 3.05 + 0.006 * soc,
        "DCPowerChargeLim": charge_lim,
        "DCPowerDischargeLim": discharge_lim,
        "DCCurrentChargeLim": charge_lim * 1000.0 / dc_voltage,
        "DCCurrentDischargeLim": discharge_lim * 1000.0 / dc_voltage,
        "TemperatureSensorXX": ambient + 1.0 + 2.0 * thermal_load,
        "MaxTemp": ambient + 2.5 + 2.0 * thermal_load,
        "MaxTempAlarm": (ambient + 2.5 + 2.0 * thermal_load > 45.0).astype(int),
        "BTMSAlarm": btm_alarm,
        "MFFPAlarm": fire_alarm,
        "FStop": fstop,
        "ActivePower": active_kw,
        "ReactivePower": reactive,
        "CosPhi": cos_phi,
        "Frequency": 50.0 + 0.015 * np.sin(2.0 * np.pi * hours / 24.0),
        "InverterState": inverter_state,
        "TotalEnergy": exported,
        "TotalImportedEnergy": imported,
        "InverterAvailability": np.full(n, 99.2),
        "Performance": perf,
        "Setpoint_ActivePower": np.clip(active_kw * 1.04, -charge_lim, discharge_lim),
        "Setpoint_ReactivePower": reactive * 1.03,
        "Temperature": hvac_temp,
        "Humidity": np.clip(52.0 - 1.6 * (hvac_temp - 22.0), 20.0, 70.0),
        "Pressure": airflow * 0.055,
        "AirFlow": airflow,
        "PowerConsumption": 18.0 + 0.009 * airflow,
        "ComponentStatus": np.where(btm_alarm == 1, "Warning", "OK"),
        "ControlSignal_Temp": np.full(n, 22.0),
        "SmokeSensorState": fire_alarm,
        "FireAlarm": fire_alarm,
        "ExtinctionDischarge": fire_alarm,
        "POI_ActivePower": active_kw - (18.0 + 0.009 * airflow),
        "POI_ReactivePower": reactive,
        "ControlMode": np.full(n, "Automático"),
        "ChargeLimitFromGrid": charge_lim,
        "DischargeLimitToGrid": discharge_lim,
    }

    if element == "PCS" and signal == "SystemStatus":
        values[signal] = inverter_state
    elif element == "FPS / SCI" and signal == "SystemStatus":
        values[signal] = np.full(n, "Armado")
    elif element == "UPS" and signal == "SystemStatus":
        values[signal] = np.full(n, "Red")
    elif element == "CT / Power Station" and signal == "SystemStatus":
        values[signal] = np.full(n, "Normal")
    elif element == "BCTRL" and signal == "ActivePower":
        values[signal] = active_kw

    return pd.DataFrame({"timestamp": timestamp, "value": values[signal], "unit": definition.unit})


def aggregate_signal(frame: pd.DataFrame, aggregation: str, frequency: str) -> pd.DataFrame:
    """Reagrupa una serie según su semántica física, no siempre por media."""
    if frame.empty or frequency == "15 min":
        return frame
    rule = {"1 hora": "h", "1 día": "D", "1 semana": "W"}[frequency]
    values = frame.set_index("timestamp")["value"]
    if not pd.api.types.is_numeric_dtype(values):
        result = values.resample(rule).last()
    elif aggregation.startswith("MAX"):
        result = values.resample(rule).max()
    elif aggregation.startswith("MIN"):
        result = values.resample(rule).min()
    elif aggregation.startswith(("LAST", "EVENTO", "ESTADO")):
        result = values.resample(rule).last()
    else:
        result = values.resample(rule).mean()
    return result.reset_index().assign(unit=frame["unit"].iloc[0])


def validate_telemetry(bundle: dict) -> list[tuple[str, bool, str]]:
    """Devuelve controles de calidad físicos y operativos del lote sintético."""
    bms_max = build_signal_series(bundle, "BMS", "MaxCellTemp")["value"]
    bms_avg = build_signal_series(bundle, "BMS", "AvgCellTemp")["value"]
    bms_min = build_signal_series(bundle, "BMS", "MinCellTemp")["value"]
    max_volt = build_signal_series(bundle, "BMS", "MaxCellVolt")["value"]
    avg_volt = build_signal_series(bundle, "BMS", "AvgCellVolt")["value"]
    min_volt = build_signal_series(bundle, "BMS", "MinCellVolt")["value"]
    soc = build_signal_series(bundle, "BMS", "SOC")["value"]
    exported = build_signal_series(bundle, "PCS", "TotalEnergy")["value"]
    imported = build_signal_series(bundle, "PCS", "TotalImportedEnergy")["value"]
    power = build_signal_series(bundle, "BMS", "DCPower")["value"]
    voltage = build_signal_series(bundle, "BMS", "DCVoltage")["value"]
    current = build_signal_series(bundle, "BMS", "DCCurrent")["value"]
    return [
        ("Temperaturas de celda", bool(((bms_max >= bms_avg) & (bms_avg >= bms_min)).all()), "Max >= Avg >= Min"),
        ("Tensiones de celda", bool(((max_volt >= avg_volt) & (avg_volt >= min_volt)).all()), "Max >= Avg >= Min"),
        ("Ventana de SOC", bool(soc.between(0.0, 100.0).all()), "0 % a 100 %"),
        ("Contadores PCS", bool((exported.diff().fillna(0) >= 0).all() and (imported.diff().fillna(0) >= 0).all()), "Monótonos"),
        ("Balance DC", bool(np.allclose(power, voltage * current / 1000.0, rtol=1e-9, atol=1e-6)), "P = V x I"),
    ]