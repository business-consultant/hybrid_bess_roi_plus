from bess_simulator.data.synthetic import generate_dashboard_dataset
from bess_simulator.data.telemetry import (
    SIGNAL_CATALOG,
    aggregate_signal,
    build_signal_series,
    validate_telemetry,
)


def _bundle():
    df = generate_dashboard_dataset(
        start_date="2024-06-01", hoy="2024-06-03", end_date="2024-06-04", seed=42,
    )
    return {
        "df": df,
        "meteo": df[["timestamp"]].assign(
            solar_elevation=0.0, ghi=100.0, ghi_clearsky=200.0, clearness_index=0.5,
            temp_ambient=25.0, wind_speed=3.0, humidity=0.5,
        ),
        "pv": df[["timestamp"]].assign(
            poa=100.0, temp_cell=30.0, p_dc_mw=5.0, p_ac_mw=4.8, p_clipped_mw=0.2,
        ),
        "params": {"rated_power_mw": 50.0},
    }


def test_every_documented_signal_generates_a_series():
    bundle = _bundle()
    for element, definitions in SIGNAL_CATALOG.items():
        for definition in definitions:
            series = build_signal_series(bundle, element, definition.name)
            assert not series.empty, f"{element}/{definition.name} no generó muestras"
            assert len(aggregate_signal(series, definition.aggregation, "1 hora")) > 0


def test_existing_operating_weather_and_pv_layers_are_selectable():
    bundle = _bundle()
    for element in ("Operación BESS", "Estación meteorológica", "Planta FV"):
        for definition in SIGNAL_CATALOG[element]:
            assert not build_signal_series(bundle, element, definition.name).empty


def test_telemetry_preserves_temperature_and_counter_invariants():
    bundle = _bundle()
    max_temp = build_signal_series(bundle, "BMS", "MaxCellTemp")["value"]
    avg_temp = build_signal_series(bundle, "BMS", "AvgCellTemp")["value"]
    min_temp = build_signal_series(bundle, "BMS", "MinCellTemp")["value"]
    assert (max_temp >= avg_temp).all()
    assert (avg_temp >= min_temp).all()

    exported = build_signal_series(bundle, "PCS", "TotalEnergy")["value"]
    imported = build_signal_series(bundle, "PCS", "TotalImportedEnergy")["value"]
    assert (exported.diff().fillna(0) >= 0).all()
    assert (imported.diff().fillna(0) >= 0).all()
    assert all(passed for _, passed, _ in validate_telemetry(bundle))