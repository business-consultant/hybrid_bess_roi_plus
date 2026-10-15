"""Vista de tendencias para las señales BESS definidas en el documento de agosto de 2026."""

from __future__ import annotations

from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

from bess_simulator.data.telemetry import (
    SIGNAL_CATALOG, aggregate_signal, build_signal_series, signal_definition,
    validate_telemetry,
)
from bess_simulator.ui.views.data_generation import ensure_active_dataset


def render_trending_charts_page() -> None:
    st.title("Trending Charts")
    st.caption("Compara hasta 12 señales sintéticas en el mismo eje temporal.")
    bundle = ensure_active_dataset()
    available_start, available_end = bundle["start"], bundle["end"]
    default_start = max(available_start, available_end - timedelta(days=7))
    signal_options = [
        f"{element} · {definition.name}"
        for element, definitions in SIGNAL_CATALOG.items()
        for definition in definitions
    ]

    plant_col, signal_col, granularity_col = st.columns([1, 3, 1])
    with plant_col:
        st.selectbox("Planta", ["Planta Híbrida 1"], key="trending_plant")
    with signal_col:
        selected_signals = st.multiselect(
            "Elementos y señales",
            signal_options,
            default=["PCS · ActivePower"],
            max_selections=12,
            key="trending_signals",
            help="Las señales se representan sincronizadas en el mismo eje temporal.",
        )
    with granularity_col:
        granularity = st.selectbox("Granularidad", ["15 min", "1 hora", "1 día", "1 semana"], key="trending_granularity")

    secondary_signals = st.multiselect(
        "Señales en eje secundario (derecha)",
        selected_signals,
        key="trending_secondary_signals",
        help="Las señales no seleccionadas aquí se representan en el eje primario izquierdo.",
    )

    selection = st.date_input(
        "Periodo", value=(default_start, available_end), min_value=available_start,
        max_value=available_end, key="trending_range",
    )
    if not isinstance(selection, tuple) or len(selection) != 2:
        st.info("Selecciona una fecha de inicio y otra de fin.")
        return
    if not selected_signals:
        st.info("Selecciona al menos una señal.")
        return

    start, end = selection
    fig = go.Figure()
    rendered = []
    primary_units = set()
    secondary_units = set()
    for index, selected in enumerate(selected_signals):
        element, signal = selected.split(" · ", maxsplit=1)
        definition = signal_definition(element, signal)
        frame = build_signal_series(bundle, element, signal)
        frame = frame[(frame["timestamp"].dt.date >= start) & (frame["timestamp"].dt.date <= end)]
        frame = aggregate_signal(frame, definition.aggregation, granularity)
        if frame.empty:
            continue
        name = f"{element} · {signal}" + (f" ({definition.unit})" if definition.unit else "")
        yaxis = "y2" if selected in secondary_signals else "y"
        if frame["value"].dtype == object:
            categories = {value: value_index for value_index, value in enumerate(sorted(frame["value"].unique()))}
            fig.add_trace(go.Scatter(
                x=frame["timestamp"], y=frame["value"].map(categories), name=name,
                mode="lines", line=dict(shape="hv", width=1.5),
                hovertemplate="%{x}<br>" + name + ": %{text}<extra></extra>", text=frame["value"], yaxis=yaxis,
            ))
        else:
            fig.add_trace(go.Scattergl(
                x=frame["timestamp"], y=frame["value"], name=name, mode="lines",
                line=dict(width=1.5), hovertemplate="%{x}<br>" + name + ": %{y:.3f}<extra></extra>", yaxis=yaxis,
            ))
        (secondary_units if yaxis == "y2" else primary_units).add(definition.unit or "sin unidad")
        rendered.append(definition)
    if not rendered:
        st.warning("No hay muestras para el periodo seleccionado.")
        return

    fig.update_layout(
        height=520, template="plotly_white", margin=dict(l=20, r=20, t=45, b=20),
        title="Tendencias seleccionadas", xaxis_title="Tiempo",
        yaxis=dict(title="Eje primario: " + ", ".join(sorted(primary_units))),
        yaxis2=dict(
            title="Eje secundario: " + ", ".join(sorted(secondary_units)),
            overlaying="y", side="right", showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)
    mixed_axes = []
    if len(primary_units) > 1:
        mixed_axes.append("primario")
    if len(secondary_units) > 1:
        mixed_axes.append("secundario")
    if mixed_axes:
        st.warning(
            "El eje " + " y ".join(mixed_axes) + " mezcla unidades. Las señales se dibujan "
            "con sus valores reales y una misma escala automática, pero no deben compararse "
            "numéricamente entre sí; usa el eje opuesto o consulta los valores en el tooltip."
        )
    st.caption(
        "Las trazas comparten eje temporal; las unidades se indican en la leyenda y en cada eje. "
        "Cada señal conserva su contrato de agregación SCADA al cambiar la granularidad."
    )

    with st.expander("Validaciones de consistencia física y de negocio", expanded=False):
        checks = validate_telemetry(bundle)
        st.dataframe(
            [{"Control": name, "Estado": "Correcto" if passed else "Error", "Regla": rule} for name, passed, rule in checks],
            use_container_width=True,
            hide_index=True,
        )