"""Vista de administración: generación y parametrización de datos sintéticos.

Perfil ADMIN / VALIDADOR. Aquí se parametriza y produce el "dataset activo"
que las vistas de operación (Dashboard, Simulador) consumen como si fueran
datos reales. El operador no edita estos parámetros.
"""

import streamlit as st
from datetime import date, timedelta

from bess_simulator.config import DEFAULTS, RANGES
from bess_simulator.data.synthetic import generate_dashboard_dataset
from bess_simulator.data.meteo import generate_meteo_dataset
from bess_simulator.data.pv import generate_pv_dataset
from bess_simulator.data.export import export_dataset_layers_to_excel
from bess_simulator.models.parameters import PvParams
from bess_simulator.storage.app_config import DEFAULT_ADVANCED_CONFIG


def _projection_params_from_simulator() -> dict:
    """Deriva los parámetros de proyección futura de la simulación del operador.

    Estos valores (spread, ciclos, RTE, degradación, DoD) son parámetros de
    SIMULACIÓN que controla el operador en el Simulador, no de generación de
    datos. Si el operador todavía no ha configurado una simulación, se usan los
    valores por defecto del modelo.
    """
    inputs = st.session_state.get("inputs")
    if inputs is not None:
        return {
            "rated_power_mw": float(inputs.bess.rated_power_mw),
            "c_rate_inverse": float(inputs.bess.c_rate_inverse),
            "avg_spread_eur": float(inputs.economic.avg_spread_price),
            "future_cycles_per_day": float(inputs.daily_cycles),
            "future_rte": float(inputs.efficiency.rte),
            "future_degradation_per_cycle": float(inputs.efficiency.degradation_per_cycle),
            "max_dod": float(inputs.efficiency.max_dod),
        }
    return {
        "rated_power_mw": float(DEFAULTS["rated_power_mw"]),
        "c_rate_inverse": float(DEFAULTS["c_rate_inverse"]),
        "avg_spread_eur": float(DEFAULTS["avg_spread_price"]),
        "future_cycles_per_day": float(DEFAULTS["year_cycles"]) / 365.0,
        "future_rte": float(DEFAULTS["rte"]),
        "future_degradation_per_cycle": float(DEFAULTS["degradation_per_cycle"]),
        "max_dod": float(DEFAULTS["max_dod"]),
    }


def _calibration_from_results() -> dict | None:
    """Deriva los agregados anuales del Simulador ROI (motor de referencia).

    Devuelve el income y el SoH final de CADA año de vida útil (índice 0 = año
    1 = histórico; resto = proyección). Conserva ROI/VAN intactos (no toca
    ``run_simulation``). Se devuelven tuplas para que sean cacheables.
    """
    results = st.session_state.get("results")
    ys = getattr(results, "yearly_summary", None) if results is not None else None
    if ys is None or ys.empty:
        return None
    return {
        "yearly_income": tuple(float(x) for x in ys["total_income"]),
        "yearly_soh_end": tuple(float(x) for x in ys["soh_end"]),
    }


# Parámetros de generación por defecto usados para el auto-arranque del Dashboard
# cuando todavía no se ha generado ningún dataset desde esta pantalla. La proyección
# futura (spread, ciclos, RTE, degradación, DoD) toma los valores por defecto del
# modelo de simulación del operador.
DEFAULT_GENERATION_PARAMS = {
    "start": date(2024, 6, 1),
    "end": date(2024, 6, 1) + timedelta(days=int(DEFAULTS["lifespan_years"]) * 365),
    "rated_power_mw": float(DEFAULTS["rated_power_mw"]),
    "c_rate_inverse": float(DEFAULTS["c_rate_inverse"]),
    "avg_spread_eur": float(DEFAULTS["avg_spread_price"]),
    "future_cycles_per_day": float(DEFAULTS["year_cycles"]) / 365.0,
    "future_rte": float(DEFAULTS["rte"]),
    "future_degradation_per_cycle": float(DEFAULTS["degradation_per_cycle"]),
    "max_dod": float(DEFAULTS["max_dod"]),
    "latitude": float(DEFAULTS["pv_latitude"]),
    "seed": 42,
}


@st.cache_data
def _cached_dataset(
    start_str, hoy_str, end_str,
    rated_power_mw, c_rate_inverse,
    avg_spread_eur, future_cycles_per_day,
    future_rte, future_degradation_per_cycle,
    max_dod, seed,
    cal_yearly_income=None, cal_yearly_soh_end=None,
):
    calibration = None
    if cal_yearly_income is not None:
        calibration = {
            "yearly_income": cal_yearly_income,
            "yearly_soh_end": cal_yearly_soh_end,
        }
    return generate_dashboard_dataset(
        start_date=start_str,
        hoy=hoy_str,
        end_date=end_str,
        rated_power_mw=rated_power_mw,
        c_rate_inverse=c_rate_inverse,
        avg_spread_eur=avg_spread_eur,
        future_cycles_per_day=future_cycles_per_day,
        future_rte=future_rte,
        future_degradation_per_cycle=future_degradation_per_cycle,
        max_dod=max_dod,
        seed=seed,
        calibration=calibration,
    )


@st.cache_data
def _cached_meteo(start_str, end_str, latitude, seed):
    """Genera (y cachea) la capa meteorológica del emplazamiento."""
    return generate_meteo_dataset(
        start_date=start_str,
        end_date=end_str,
        latitude=latitude,
        cfg=DEFAULT_ADVANCED_CONFIG,
        seed=seed,
    )


@st.cache_data
def _cached_reference_pv(start_str, end_str, latitude, seed):
    """Perfil PV de referencia (PvParams por defecto) sobre la meteo del sitio.

    Sirve de vista previa; la generación PV con el dimensionado real del
    operador se aplica en el motor de despacho (Fase 5).
    """
    meteo_df = _cached_meteo(start_str, end_str, latitude, seed)
    return generate_pv_dataset(meteo_df, PvParams(), DEFAULT_ADVANCED_CONFIG)


def build_active_dataset(params: dict, calibration: dict | None = None) -> dict:
    """Genera el dataset y lo empaqueta con sus metadatos.

    Devuelve un dict almacenable en ``st.session_state['active_dataset']``. Si se
    pasa ``calibration`` (agregados del Simulador ROI), el dataset converge a
    esos valores conservando la variabilidad estocástica.
    """
    start = params["start"]
    end = params["end"]
    hoy = params.get("hoy")
    if hoy is None:
        hoy = start + timedelta(days=365)
        if hoy > end:
            hoy = start + (end - start) // 2

    cal = calibration or {}
    df = _cached_dataset(
        str(start), str(hoy), str(end),
        rated_power_mw=params["rated_power_mw"],
        c_rate_inverse=params["c_rate_inverse"],
        avg_spread_eur=float(params["avg_spread_eur"]),
        future_cycles_per_day=float(params["future_cycles_per_day"]),
        future_rte=float(params["future_rte"]),
        future_degradation_per_cycle=float(params["future_degradation_per_cycle"]),
        max_dod=float(params["max_dod"]),
        seed=params["seed"],
        cal_yearly_income=cal.get("yearly_income"),
        cal_yearly_soh_end=cal.get("yearly_soh_end"),
    )

    latitude = float(params.get("latitude", DEFAULTS["pv_latitude"]))
    # La capa meteo/PV (realidad del sitio para monitorización de subelementos)
    # se acota a ~1 año de proyección; no necesita cubrir toda la vida útil.
    meteo_end = min(end, hoy + timedelta(days=365))
    meteo_df = _cached_meteo(str(start), str(meteo_end), latitude, params["seed"])
    pv_df = _cached_reference_pv(str(start), str(meteo_end), latitude, params["seed"])

    return {
        "df": df,
        "meteo": meteo_df,
        "pv": pv_df,
        "start": start,
        "hoy": hoy,
        "end": end,
        "params": dict(params, hoy=hoy),
        "label": f"{start} → {hoy} → {end}",
    }


def ensure_active_dataset() -> dict:
    """Devuelve el dataset activo; si no existe, lo genera con defaults.

    Permite que las vistas de operación arranquen sin pantalla vacía la
    primera vez (auto-generación con parámetros por defecto).
    """
    if "active_dataset" not in st.session_state:
        st.session_state["active_dataset"] = build_active_dataset(DEFAULT_GENERATION_PARAMS)
    return st.session_state["active_dataset"]


def _generation_params_from_inputs() -> dict:
    """Parámetros de generación derivados del escenario del operador.

    Toma el dimensionado y los parámetros de operación del Simulador
    (potencia, c-rate, spread, ciclos, RTE, degradación, DoD) y conserva el
    rango temporal / emplazamiento / semilla de los defaults. Si todavía no
    hay simulación, devuelve los defaults del modelo.
    """
    params = dict(DEFAULT_GENERATION_PARAMS)
    params.update(_projection_params_from_simulator())
    # La proyección abarca toda la vida útil parametrizada: 1 año de histórico
    # (año 1 vivido) + (lifespan-1) años de proyección.
    inputs = st.session_state.get("inputs")
    lifespan = int(inputs.bess.lifespan_years) if inputs is not None else int(DEFAULTS["lifespan_years"])
    start = params["start"]
    params["hoy"] = start + timedelta(days=365)
    params["end"] = start + timedelta(days=lifespan * 365)
    return params


def rebuild_active_dataset_from_simulation() -> dict:
    """Botonazo de coherencia: regenera el dataset activo desde el escenario.

    Usa los parámetros del operador (Simulador) para histórico + proyección y
    calibra los agregados a los años 1–2 del Simulador ROI. Así el Dashboard
    Histórico BESS refleja el escenario simulado (deja de estar stale).
    """
    params = _generation_params_from_inputs()
    calibration = _calibration_from_results()
    bundle = build_active_dataset(params, calibration)
    st.session_state["active_dataset"] = bundle
    return bundle


def render_data_generation_page():
    from bess_simulator.ui.components.sticky_header import render_sticky_header
    render_sticky_header("Generación de Datos Sintéticos")

    st.caption(
        "Pantalla de **administración / validación del prototipo**. Aquí se parametriza y "
        "genera el dataset sintético que las pantallas de operación consumen como si fueran "
        "datos reales. El operador no edita estos parámetros."
    )

    # --- Rango temporal y frontera HOY ---
    col_dates, col_gran = st.columns([3, 2])
    with col_dates:
        date_range = st.date_input(
            "Rango de operación",
            value=(DEFAULT_GENERATION_PARAMS["start"], DEFAULT_GENERATION_PARAMS["end"]),
            min_value=date(2020, 1, 1),
            max_value=date(2045, 12, 31),
            key="gen_date_range",
            help="Período total del dataset. Antes de HOY = histórico sintético, después = proyección",
        )

    if not isinstance(date_range, tuple) or len(date_range) != 2:
        st.warning("Selecciona un rango de fechas válido.")
        return

    start, end = date_range

    default_hoy = start + timedelta(days=365)
    if default_hoy > end:
        default_hoy = start + (end - start) // 2

    hoy = st.date_input(
        "Fecha HOY (frontera histórico / proyección)",
        value=default_hoy,
        min_value=start,
        max_value=end,
        key="gen_hoy",
        help="Frontera entre datos históricos (modelado experto OMIE) y proyección (parámetros del Simulador)",
    )
    st.caption(
        "Los datos **antes de HOY** son históricos sintéticos (modelado experto BESS + OMIE). "
        "Los datos **desde HOY** son proyección que usa los **parámetros de simulación del operador** "
        "(spread, ciclos, RTE, degradación y DoD se editan en el **Simulador**, no aquí)."
    )

    # --- Emplazamiento / capa meteorológica (realidad del sitio) ---
    with st.expander("Emplazamiento y meteorología", expanded=False):
        st.caption(
            "Propiedades físicas del emplazamiento que definen el recurso solar (la \"realidad\" "
            "del sitio). Alimentan la generación PV y la monitorización de subelementos. "
            "El **dimensionado** de la PV y la red es decisión del operador (en el Simulador)."
        )
        latitude = st.slider(
            "Latitud (°)",
            min_value=float(RANGES["pv_latitude"][0]),
            max_value=float(RANGES["pv_latitude"][1]),
            value=float(DEFAULTS["pv_latitude"]),
            step=1.0,
            key="gen_latitude",
            help="Latitud del emplazamiento. Determina la geometría solar (elevación) y por tanto la irradiancia de cielo claro generada",
        )

    # --- Proyección futura: tomada de los parámetros del Simulador (operador) ---
    proj = _projection_params_from_simulator()
    with st.expander("Proyección futura (parámetros del Simulador)", expanded=False):
        st.caption(
            "Estos valores son **parámetros de simulación** y se editan en el **Simulador** "
            "(operador). Aquí se muestran solo para referencia del dataset que se generará."
        )
        ref = "de la simulación actual" if st.session_state.get("inputs") is not None else "por defecto del modelo"
        st.caption(f"Origen de los valores: **{ref}**.")
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Spread medio", f"{proj['avg_spread_eur']:.0f} €/MWh")
        rc2.metric("Ciclos equiv./día", f"{proj['future_cycles_per_day']:.2f}")
        rc3.metric("RTE esperado", f"{proj['future_rte'] * 100:.1f} %")
        rc4, rc5, _ = st.columns(3)
        rc4.metric("Degradación/ciclo", f"{proj['future_degradation_per_cycle'] * 100:.4f} %")
        rc5.metric("DoD máximo", f"{proj['max_dod'] * 100:.0f} %")

    params = {
        "start": start, "hoy": hoy, "end": end,
        **proj,
        "latitude": float(latitude),
        "seed": 42,
    }
    calibration = _calibration_from_results()

    st.divider()

    # --- Estado del dataset activo ---
    active = st.session_state.get("active_dataset")
    if active is not None:
        st.info(f"**Dataset activo:** {active['label']} — consumido por Dashboard y Simulador.")
        meteo_df = active.get("meteo")
        pv_df = active.get("pv")
        if meteo_df is not None and not meteo_df.empty:
            ghi_mean = float(meteo_df["ghi"].mean())
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("GHI medio", f"{ghi_mean:.0f} W/m²", help="Irradiancia horizontal global media de la serie generada")
            mc2.metric("Temp. ambiente media", f"{float(meteo_df['temp_ambient'].mean()):.1f} °C")
            if pv_df is not None and not pv_df.empty:
                pv_energy_gwh = float(pv_df["p_ac_mw"].sum()) * 0.25 / 1000.0
                mc3.metric("Energía PV ref. (PvParams def.)", f"{pv_energy_gwh:,.1f} GWh", help="Energía AC del perfil PV de referencia (dimensionado por defecto). El dimensionado real lo fija el operador")
    else:
        st.info("Aún no hay dataset activo. Pulsa **Generar dataset** para crear uno.")

    col_gen, col_save = st.columns(2)
    with col_gen:
        if st.button("Generar dataset", type="primary", use_container_width=True,
                     help="Genera el dataset sintético y lo fija como dataset activo"):
            with st.spinner("Generando datos sintéticos..."):
                st.session_state["active_dataset"] = build_active_dataset(params, calibration)
            st.success("Dataset generado y fijado como activo.")
            st.rerun()

    with col_save:
        dataset_name = st.text_input("Nombre", key="gen_save_name", placeholder="Ej: Jarama junio")
        if st.button("Guardar dataset en BD", type="secondary", use_container_width=True,
                     help="Persiste el dataset (histórico + proyección) para consulta posterior"):
            with st.spinner("Generando y guardando..."):
                bundle = build_active_dataset(params, calibration)
                st.session_state["active_dataset"] = bundle
                dash_repo = st.session_state["dash_repo"]
                save_params = {
                    "asset": "",
                    "start_date": str(start), "hoy": str(hoy), "end_date": str(end),
                    "rated_power_mw": float(proj["rated_power_mw"]),
                    "c_rate_inverse": float(proj["c_rate_inverse"]),
                    "avg_spread_eur": float(proj["avg_spread_eur"]),
                    "future_cycles_per_day": float(proj["future_cycles_per_day"]),
                    "future_rte": float(proj["future_rte"]),
                    "future_degradation_per_cycle": float(proj["future_degradation_per_cycle"]),
                    "max_dod": float(proj["max_dod"]),
                    "seed": 42,
                }
                run_id = dash_repo.save(save_params, bundle["df"], name=dataset_name or None)
            st.success(f"Dataset guardado: {dataset_name or run_id[:8]}")

    # --- Exportación de las 3 capas (Excel multihoja, 15 min) ---
    st.divider()
    if active is not None:
        st.download_button(
            "Exportar 3 capas (Excel, 15 min)",
            data=export_dataset_layers_to_excel(active),
            file_name=f"dataset_capas_{start}_{end}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Descarga BESS, meteorología y generación PV (resolución 15 min) en un único Excel multihoja",
        )
    else:
        st.caption("Genera un dataset para habilitar la exportación de las 3 capas.")
