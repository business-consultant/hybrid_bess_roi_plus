"""Tests de los snapshots por subelemento (engine/elements.py, Fase 7)."""

import pytest

from bess_simulator.ui.views.data_generation import (
    build_active_dataset, DEFAULT_GENERATION_PARAMS,
)
from bess_simulator.engine.plant import compute_plant_summary
from bess_simulator.models.parameters import SimulationInputs, PvParams
from bess_simulator.engine import elements


@pytest.fixture(scope="module")
def bundle():
    return build_active_dataset(DEFAULT_GENERATION_PARAMS)


@pytest.fixture(scope="module")
def summary(bundle):
    inputs = SimulationInputs(pv=PvParams(latitude=40.0))
    return compute_plant_summary(bundle, inputs)


class TestBessSnapshot:
    def test_row_count_matches_modules(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        assert len(snap) == max(1, int(summary.bess_modules))

    def test_columns(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        expected = {
            "Estado", "Nombre", "Carga", "SoC (%)", "SoH (%)", "DoD máx. (%)",
            "Tª máx. celda (°C)", "Desv. máx. tensión celda (mV)",
            "Intensidad máx. (A)", "Ciclos equiv.", "_status",
        }
        assert set(snap.columns) == expected

    def test_battery_glyph_reflects_soc(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        # Cada celda de carga lleva un icono de pila y una barra de 5 segmentos.
        for carga in snap["Carga"]:
            assert carga[0] in ("🔋", "🪫")
            bar = carga.split(" ", 1)[1]
            assert len(bar) == 5
            assert set(bar) <= {"▰", "▱"}

    def test_deterministic(self, summary, bundle):
        a = elements.build_bess_snapshot(summary, bundle["df"])
        b = elements.build_bess_snapshot(summary, bundle["df"])
        assert a.equals(b)

    def test_status_counts_sum(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        counts = elements.status_counts(snap)
        assert sum(counts.values()) == len(snap)

    def test_temp_threshold_drives_status(self, summary, bundle):
        """Un umbral crítico muy bajo debe marcar fallos; uno alto, ninguno."""
        low = elements.build_bess_snapshot(summary, bundle["df"], temp_critical_c=20.0)
        high = elements.build_bess_snapshot(summary, bundle["df"], temp_critical_c=80.0)
        assert elements.status_counts(low)[elements.STATUS_FAULT] > 0
        assert elements.status_counts(high)[elements.STATUS_FAULT] == 0

    def test_ranges(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        assert snap["SoH (%)"].between(80.0, 100.0).all()
        assert snap["SoC (%)"].between(0.0, 100.0).all()
        assert (snap["Intensidad máx. (A)"] >= 0).all()


class TestBessWarrantyKpis:
    def test_titles(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        kpis = elements.build_bess_warranty_kpis(snap)
        titles = [k["title"] for k in kpis]
        assert titles == [
            "SoH mínimo", "SoH spread (grupo)", "Desvío máx. SoH",
            "Desvío máx. Tª", "Intensidad máxima", "Desv. máx. tensión celda",
            "DoD máx. (grupo)", "Tª máx. celda absoluta", "Ciclos equiv. máx.",
        ]

    def test_card_shape(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        for kpi in elements.build_bess_warranty_kpis(snap):
            assert set(kpi.keys()) == {"title", "value", "element", "status", "limit"}
            assert kpi["value"] and kpi["element"]

    def test_status_values_are_valid(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        valid = {
            None,
            elements.STATUS_AVAILABLE,
            elements.STATUS_WARNING,
            elements.STATUS_FAULT,
        }
        for kpi in elements.build_bess_warranty_kpis(snap):
            assert kpi["status"] in valid

    def test_informational_cards_have_no_status(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        kpis = elements.build_bess_warranty_kpis(snap)
        info_titles = {
            "Desvío máx. SoH", "Desvío máx. Tª",
            "Intensidad máxima", "Desv. máx. tensión celda",
        }
        for kpi in kpis:
            if kpi["title"] in info_titles:
                assert kpi["status"] is None and kpi["limit"] is None
            else:
                assert kpi["status"] is not None and kpi["limit"]

    def test_soh_floor_drives_fault(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        # Suelo de garantía por encima del SoH mínimo real → fallo.
        floor = float(snap["SoH (%)"].min()) + 5.0
        kpis = elements.build_bess_warranty_kpis(snap, {"soh_min": floor})
        card = next(k for k in kpis if k["title"] == "SoH mínimo")
        assert card["status"] == elements.STATUS_FAULT
        # Suelo holgado por debajo → disponible.
        kpis_ok = elements.build_bess_warranty_kpis(snap, {"soh_min": 50.0})
        card_ok = next(k for k in kpis_ok if k["title"] == "SoH mínimo")
        assert card_ok["status"] == elements.STATUS_AVAILABLE

    def test_cycles_tope_drives_fault(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        tope = float(snap["Ciclos equiv."].max()) - 1.0
        kpis = elements.build_bess_warranty_kpis(snap, {"cycles_max": tope})
        card = next(k for k in kpis if k["title"] == "Ciclos equiv. máx.")
        assert card["status"] == elements.STATUS_FAULT

    def test_soh_min_matches_worst_module(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        kpis = elements.build_bess_warranty_kpis(snap)
        soh_min_card = next(k for k in kpis if k["title"] == "SoH mínimo")
        worst = snap.loc[snap["SoH (%)"].idxmin(), "Nombre"]
        assert soh_min_card["element"] == worst

    def test_max_current_matches_module(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        kpis = elements.build_bess_warranty_kpis(snap)
        card = next(k for k in kpis if k["title"] == "Intensidad máxima")
        top = snap.loc[snap["Intensidad máx. (A)"].idxmax(), "Nombre"]
        assert card["element"] == top

    def test_cycles_kpi_matches_module(self, summary, bundle):
        snap = elements.build_bess_snapshot(summary, bundle["df"])
        kpis = elements.build_bess_warranty_kpis(snap)
        card = next(k for k in kpis if k["title"] == "Ciclos equiv. máx.")
        top = snap.loc[snap["Ciclos equiv."].idxmax(), "Nombre"]
        assert card["element"] == top

    def test_empty_snapshot(self):
        import pandas as pd
        assert elements.build_bess_warranty_kpis(pd.DataFrame()) == []


class TestPcsSnapshot:
    def test_row_count_matches_pcs(self, summary, bundle):
        snap = elements.build_pcs_snapshot(summary, bundle["df"])
        assert len(snap) == max(1, int(summary.pcs))

    def test_columns(self, summary, bundle):
        snap = elements.build_pcs_snapshot(summary, bundle["df"])
        expected = {
            "Estado", "Nombre", "PR inversor (%)",
            "Producción (MWh)", "Disponibilidad (%)", "_status",
        }
        assert set(snap.columns) == expected

    def test_deterministic(self, summary, bundle):
        a = elements.build_pcs_snapshot(summary, bundle["df"])
        b = elements.build_pcs_snapshot(summary, bundle["df"])
        assert a.equals(b)

    def test_production_sums_near_total(self, summary, bundle):
        snap = elements.build_pcs_snapshot(summary, bundle["df"])
        total = float(summary.exported_gwh) * 1000.0
        # El reparto por inversor (±10%) debe rondar el total exportado.
        assert snap["Producción (MWh)"].sum() == pytest.approx(total, rel=0.12)

    def test_ranges(self, summary, bundle):
        snap = elements.build_pcs_snapshot(summary, bundle["df"])
        assert snap["PR inversor (%)"].between(70.0, 99.0).all()
        assert snap["Disponibilidad (%)"].between(80.0, 100.0).all()


class TestPcsPowerSeries:
    def test_one_column_per_inverter(self, summary, bundle):
        series = elements.build_pcs_power_series(summary, bundle)
        assert not series.empty
        inverter_cols = [c for c in series.columns if c != "timestamp"]
        assert len(inverter_cols) == max(1, int(summary.pcs))

    def test_deterministic(self, summary, bundle):
        a = elements.build_pcs_power_series(summary, bundle)
        b = elements.build_pcs_power_series(summary, bundle)
        assert a.equals(b)

    def test_specific_power_is_per_unit(self, summary, bundle):
        series = elements.build_pcs_power_series(summary, bundle)
        inverter_cols = [c for c in series.columns if c != "timestamp"]
        values = series[inverter_cols].to_numpy()
        # Potencia específica (AC/DC instalada) es no negativa y < 1 p.u.
        assert (values >= 0.0).all()
        assert values.max() < 1.0

    def test_empty_without_pv(self, summary):
        assert elements.build_pcs_power_series(summary, {"pv": None}).empty
        assert elements.build_pcs_power_series(summary, None).empty


class TestPanelData:
    def test_keys(self, summary, bundle):
        panel = elements.build_panel_data(summary, bundle["df"])
        expected = {
            "active_power_mw", "reactive_power_mvar", "power_factor",
            "energy_exported_mwh", "energy_imported_mwh", "capacity_factor_pct",
        }
        assert set(panel.keys()) == expected

    def test_power_factor_range(self, summary, bundle):
        panel = elements.build_panel_data(summary, bundle["df"])
        assert 0.9 <= panel["power_factor"] <= 1.0

    def test_capacity_factor_realistic(self, summary, bundle):
        # CF de planta híbrida PV-BESS sobre el punto de conexión: no debe
        # saturar al tope antiguo de 99.9 % ni superar el 100 %.
        panel = elements.build_panel_data(summary, bundle["df"])
        cf = panel["capacity_factor_pct"]
        assert 0.0 < cf < 60.0


class TestMeteoPyranometers:
    def test_columns_and_sensor_count(self, bundle):
        pyr = elements.build_meteo_pyranometers(bundle["meteo"], n_sensors=3)
        assert not pyr.empty
        for i in (1, 2, 3):
            assert f"ghi_p{i}" in pyr.columns
            assert f"gpoa_p{i}" in pyr.columns
        assert "ghi_clearsky" in pyr.columns

    def test_gpoa_above_ghi(self, bundle):
        # El plano de módulos recibe más irradiancia que el plano horizontal.
        pyr = elements.build_meteo_pyranometers(bundle["meteo"])
        assert pyr["gpoa_p1"].mean() > pyr["ghi_p1"].mean()

    def test_sensors_differ_but_close(self, bundle):
        pyr = elements.build_meteo_pyranometers(bundle["meteo"])
        m1, m2 = pyr["ghi_p1"].mean(), pyr["ghi_p2"].mean()
        assert m1 != m2
        assert abs(m1 - m2) / max(m1, 1e-9) < 0.1

    def test_deterministic(self, bundle):
        a = elements.build_meteo_pyranometers(bundle["meteo"])
        b = elements.build_meteo_pyranometers(bundle["meteo"])
        assert a.equals(b)

    def test_native_15min_resolution(self, bundle):
        # No debe colapsar a media diaria: conserva el grano de 15 min, una fila
        # por muestra de la serie meteorológica original.
        import pandas as pd
        meteo = bundle["meteo"]
        pyr = elements.build_meteo_pyranometers(meteo)
        assert len(pyr) == len(meteo)
        deltas = pyr["timestamp"].sort_values().diff().dropna().unique()
        assert len(deltas) == 1
        assert deltas[0] == pd.Timedelta(minutes=15)

    def test_empty_input(self):
        import pandas as pd
        out = elements.build_meteo_pyranometers(pd.DataFrame())
        assert out.empty


class TestHvacSnapshot:
    def test_row_count_matches_containers(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        assert len(snap) == elements.n_containers(summary)

    def test_columns(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        expected = {
            "Estado", "Contenedor", "COP", "Uniformidad ΔT (°C)",
            "Consumo (MWh)", "Consumo (% BESS)", "Disponibilidad (%)", "_status",
        }
        assert set(snap.columns) == expected

    def test_deterministic(self, summary, bundle):
        a = elements.build_hvac_snapshot(summary, bundle["df"])
        b = elements.build_hvac_snapshot(summary, bundle["df"])
        assert a.equals(b)

    def test_ranges(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        assert snap["COP"].between(2.0, 5.0).all()
        assert snap["Uniformidad ΔT (°C)"].between(0.5, 9.5).all()
        assert snap["Disponibilidad (%)"].between(90.0, 100.0).all()
        assert (snap["Consumo (MWh)"] >= 0).all()

    def test_status_counts_sum(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        counts = elements.status_counts(snap)
        assert sum(counts.values()) == len(snap)

    def test_container_count_scales_with_capacity(self, summary):
        few = elements.n_containers(summary, {"container_mwh": 1000.0})
        many = elements.n_containers(summary, {"container_mwh": 1.0})
        assert few == 1
        assert many >= few


class TestHvacKpis:
    def test_titles(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        kpis = elements.build_hvac_kpis(snap, summary)
        assert [k["title"] for k in kpis] == [
            "COP medio (enfriamiento)", "Uniformidad de temperatura",
            "Consumo energético HVAC", "Disponibilidad HVAC",
        ]

    def test_card_shape(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        for kpi in elements.build_hvac_kpis(snap, summary):
            assert set(kpi.keys()) == {
                "title", "value", "element", "status", "limit", "help",
            }
            assert kpi["value"] and kpi["element"] and kpi["help"]

    def test_status_values_are_valid(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        valid = {
            None, elements.STATUS_AVAILABLE,
            elements.STATUS_WARNING, elements.STATUS_FAULT,
        }
        for kpi in elements.build_hvac_kpis(snap, summary):
            assert kpi["status"] in valid

    def test_cop_target_drives_status(self, summary, bundle):
        snap = elements.build_hvac_snapshot(summary, bundle["df"])
        cop_mean = float(snap["COP"].mean())
        # Objetivo de COP muy alto → la tarjeta de COP marca fallo.
        kpis = elements.build_hvac_kpis(snap, summary, {"cop_target": cop_mean + 1.0})
        card = next(k for k in kpis if k["title"] == "COP medio (enfriamiento)")
        assert card["status"] == elements.STATUS_FAULT

    def test_empty_snapshot(self):
        import pandas as pd
        assert elements.build_hvac_kpis(pd.DataFrame(), summary=None) == []


class TestHvacConsumptionSeries:
    def test_columns(self, summary, bundle):
        series = elements.build_hvac_consumption_series(summary, bundle)
        assert list(series.columns) == ["timestamp", "consumo_mwh", "pct_bess"]
        assert not series.empty

    def test_deterministic(self, summary, bundle):
        a = elements.build_hvac_consumption_series(summary, bundle)
        b = elements.build_hvac_consumption_series(summary, bundle)
        assert a.equals(b)

    def test_non_negative(self, summary, bundle):
        series = elements.build_hvac_consumption_series(summary, bundle)
        assert (series["consumo_mwh"] >= 0).all()
        assert (series["pct_bess"] >= 0).all()

    def test_empty_without_bundle(self, summary):
        assert elements.build_hvac_consumption_series(summary, None).empty
