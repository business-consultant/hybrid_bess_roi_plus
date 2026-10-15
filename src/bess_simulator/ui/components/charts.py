import plotly.graph_objects as go
import pandas as pd
from bess_simulator.i18n import t
from bess_simulator.models.results import SimulationResults, SensitivityResult


def chart_yearly_income_costs(yearly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=yearly["year"], y=yearly["total_income"], name=t("Ingresos", "Income"), marker_color="#28a745"))
    fig.add_trace(go.Bar(x=yearly["year"], y=yearly["total_opex"], name="OPEX", marker_color="#dc3545"))
    fig.update_layout(title=t("Ingresos vs OPEX por año", "Income vs OPEX by year"), barmode="group", xaxis_title=t("Año", "Year"), yaxis_title="€", template="plotly_white")
    return fig


def chart_soh_evolution(yearly: pd.DataFrame, soh_min: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=yearly["year"], y=yearly["soh_end"] * 100, mode="lines+markers", name="SoH", line=dict(color="#007bff", width=2)))
    fig.add_hline(y=soh_min * 100, line_dash="dash", line_color="red", annotation_text=t(f"SoH mín ({soh_min:.0%})", f"Min SoH ({soh_min:.0%})"))
    fig.update_layout(title=t("Evolución del State of Health", "State of Health evolution"), xaxis_title=t("Año", "Year"), yaxis_title="SoH (%)", template="plotly_white", yaxis_range=[50, 105])
    return fig


def chart_cash_flow(yearly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=yearly["year"], y=yearly["accumulated_dcf"], mode="lines+markers", name=t("Cash Flow Acumulado", "Accumulated Cash Flow"), line=dict(color="#6f42c1", width=2), fill="tozeroy"))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(title=t("Cash Flow Acumulado Descontado", "Accumulated Discounted Cash Flow"), xaxis_title=t("Año", "Year"), yaxis_title="€", template="plotly_white")
    return fig


def chart_degradation_rte(yearly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=yearly["year"], y=yearly["avg_degradation"] * 100, mode="lines+markers", name=t("Degradación media", "Average degradation"), yaxis="y", line=dict(color="#fd7e14")))
    fig.add_trace(go.Scatter(x=yearly["year"], y=yearly["avg_rte"] * 100, mode="lines+markers", name=t("RTE media", "Average RTE"), yaxis="y2", line=dict(color="#20c997")))
    fig.update_layout(
        title=t("Degradación y RTE por año", "Degradation and RTE by year"),
        xaxis_title=t("Año", "Year"),
        yaxis=dict(title=t("Degradación (%)", "Degradation (%)"), side="left"),
        yaxis2=dict(title="RTE (%)", overlaying="y", side="right"),
        template="plotly_white",
    )
    return fig


def chart_sensitivity_heatmap(sensitivity: SensitivityResult) -> go.Figure:
    matrix = sensitivity.matrix
    fig = go.Figure(data=go.Heatmap(
        z=matrix.values * 100,
        x=matrix.columns,
        y=[f"{p} €/MWh" for p in sensitivity.price_values],
        colorscale="RdYlGn",
        text=[[f"{v * 100:.1f}%" for v in row] for row in matrix.values],
        texttemplate="%{text}",
        textfont={"size": 11},
        colorbar=dict(title="ROI (%)"),
    ))
    fig.update_layout(title=t("Matriz de Sensibilidad (ROI)", "Sensitivity Matrix (ROI)"), xaxis_title=t("OPEX (€/MW·año)", "OPEX (€/MW·year)"), yaxis_title=t("Precio retribución (€/MWh)", "Retribution price (€/MWh)"), template="plotly_white")
    return fig


# ---------------------------------------------------------------------------
# Dashboard charts — régimen dual pasado/futuro con línea HOY
# ---------------------------------------------------------------------------

def _add_hoy_vline(fig: go.Figure, hoy: pd.Timestamp) -> None:
    hoy_str = str(hoy)
    fig.add_shape(
        type="line", x0=hoy_str, x1=hoy_str, y0=0, y1=1,
        yref="paper", line=dict(dash="dash", color="red", width=2),
    )
    fig.add_annotation(
        x=hoy_str, y=1, yref="paper",
        text=t("HOY", "TODAY"), showarrow=False,
        font=dict(size=13, color="red"),
        yshift=10,
    )


def _add_dual_traces(
    fig: go.Figure,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    name: str,
    color: str,
    yaxis: str = "y",
) -> None:
    hist = df[~df["is_forecast"]]
    fore = df[df["is_forecast"]]
    fig.add_trace(go.Scattergl(
        x=hist[x_col], y=hist[y_col],
        name=name, legendgroup=name,
        line=dict(color=color, width=2, dash="solid"),
        yaxis=yaxis,
    ))
    if not fore.empty:
        fig.add_trace(go.Scattergl(
            x=fore[x_col], y=fore[y_col],
            name=f"{name} ({t('proy.', 'fcst.')})", legendgroup=name,
            showlegend=True,
            line=dict(color=color, width=2, dash="dash"),
            yaxis=yaxis,
        ))


def chart_dashboard_prices_income(df: pd.DataFrame, hoy: pd.Timestamp) -> go.Figure:
    fig = go.Figure()
    _add_dual_traces(fig, df, "timestamp", "capture_price", "Capture Price", "#e67e22")
    _add_dual_traces(fig, df, "timestamp", "average_market_price", "Market Price", "#3498db")
    _add_dual_traces(fig, df, "timestamp", "income", t("Ingresos", "Income"), "#2ecc71", yaxis="y2")
    _add_hoy_vline(fig, hoy)
    fig.update_layout(
        template="plotly_white",
        yaxis=dict(title="€/MWh", side="left"),
        yaxis2=dict(title="€", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center"),
        height=500,
        margin=dict(t=30),
    )
    # Proyección completa a vida útil; zoom para acotar (p.ej. 1 año).
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.06),
        rangeselector=dict(
            buttons=[
                dict(count=1, label=t("1a", "1y"), step="year", stepmode="backward"),
                dict(count=5, label=t("5a", "5y"), step="year", stepmode="backward"),
                dict(step="all", label=t("Todo", "All")),
            ],
            x=0, y=1.12, xanchor="left", yanchor="top",
        ),
    )
    return fig


def chart_dashboard_soh(df: pd.DataFrame, hoy: pd.Timestamp) -> go.Figure:
    fig = go.Figure()
    _add_dual_traces(fig, df, "timestamp", "soh", "SoH", "#007bff")
    _add_hoy_vline(fig, hoy)
    fig.add_hline(y=0.75, line_dash="dot", line_color="red", annotation_text=t("SoH mín (75%)", "Min SoH (75%)"))
    fig.update_layout(
        title=t("Evolución del State of Health", "State of Health evolution"),
        template="plotly_white",
        yaxis=dict(title="SoH", range=[0.50, 1.05]),
        height=400,
    )
    return fig


def chart_dashboard_rte(df: pd.DataFrame, hoy: pd.Timestamp) -> go.Figure:
    fig = go.Figure()
    _add_dual_traces(fig, df, "timestamp", "rte", "RTE", "#20c997")
    _add_hoy_vline(fig, hoy)
    fig.update_layout(
        title=t("Evolución del Round-Trip Efficiency", "Round-Trip Efficiency evolution"),
        template="plotly_white",
        yaxis=dict(title="RTE", range=[0.70, 0.96]),
        height=400,
    )
    return fig


def chart_dashboard_cycles(df: pd.DataFrame, hoy: pd.Timestamp) -> go.Figure:
    fig = go.Figure()
    cumulative = df["cycles"].cumsum()
    hist_mask = ~df["is_forecast"]
    fore_mask = df["is_forecast"]
    fig.add_trace(go.Scattergl(
        x=df.loc[hist_mask, "timestamp"], y=cumulative[hist_mask],
        name=t("Ciclos acum.", "Cum. cycles"), legendgroup="cycles",
        line=dict(color="#6f42c1", width=2, dash="solid"),
    ))
    if fore_mask.any():
        fig.add_trace(go.Scattergl(
            x=df.loc[fore_mask, "timestamp"], y=cumulative[fore_mask],
            name=t("Ciclos acum. (proy.)", "Cum. cycles (fcst.)"), legendgroup="cycles",
            line=dict(color="#6f42c1", width=2, dash="dash"),
        ))
    _add_hoy_vline(fig, hoy)
    fig.update_layout(
        title=t("Ciclos Equivalentes Acumulados", "Accumulated Equivalent Cycles"),
        template="plotly_white",
        yaxis_title=t("FEC acumulados", "Accumulated FEC"),
        height=400,
    )
    return fig


def chart_dashboard_temperature(df: pd.DataFrame, hoy: pd.Timestamp) -> go.Figure:
    fig = go.Figure()
    _add_dual_traces(fig, df, "timestamp", "temperature", t("Temperatura", "Temperature"), "#fd7e14")
    _add_hoy_vline(fig, hoy)
    fig.update_layout(
        title=t("Temperatura Operativa", "Operating Temperature"),
        template="plotly_white",
        yaxis=dict(title="°C", range=[15, 42]),
        height=400,
    )
    return fig


# ---------------------------------------------------------------------------
# Planta híbrida — pantalla general (Fase 6)
# ---------------------------------------------------------------------------

def chart_plant_energy_split(exported_pct: float, imported_pct: float) -> go.Figure:
    """Barra horizontal exportada/importada (estilo 'Total energy delivered')."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=[""], x=[imported_pct], orientation="h", name=t("Importada", "Imported"),
        marker_color="#aee3f0", text=[f"−{imported_pct:.2f} %"],
        textposition="inside", insidetextanchor="middle", hoverinfo="x",
    ))
    fig.add_trace(go.Bar(
        y=[""], x=[exported_pct], orientation="h", name=t("Exportada", "Exported"),
        marker_color="#17a2b8", text=[f"{exported_pct:.2f} %"],
        textposition="inside", insidetextanchor="middle", hoverinfo="x",
    ))
    fig.update_layout(
        barmode="stack", template="plotly_white",
        height=90, margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def chart_plant_production(daily: pd.DataFrame, x_range=None) -> go.Figure:
    """Producción diaria: barras de carga (−)/descarga (+) + línea de SoH."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["date"], y=daily["discharge_mwh"], name=t("Descarga", "Discharge"),
        marker_color="#17a2b8",
    ))
    fig.add_trace(go.Bar(
        x=daily["date"], y=daily["charge_mwh"], name=t("Carga", "Charge"),
        marker_color="#aee3f0",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["soh"] * 100, name="SoH",
        yaxis="y2", line=dict(color="#e83e8c", width=2),
    ))
    xaxis = dict(title=t("Tiempo", "Time"), type="date")
    if x_range is not None:
        xaxis["range"] = list(x_range)
    fig.update_layout(
        barmode="relative", template="plotly_white",
        xaxis=xaxis,
        yaxis=dict(title="MWh"),
        yaxis2=dict(title="SoH (%)", overlaying="y", side="right", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center"),
        height=380, margin=dict(t=20),
    )
    return fig


def chart_power_soc_series(series: pd.DataFrame, x_range=None) -> go.Figure:
    """Serie temporal continua: potencia PV + carga/descarga BESS + potencia POI + SoC.

    Comparte el eje temporal (X) con la gráfica de producción de arriba. El eje
    izquierdo está en MW (PV, BESS y POI); el derecho en % (SoC).
    """
    fig = go.Figure()
    if series is None or series.empty:
        fig.update_layout(template="plotly_white", height=420)
        return fig

    fig.add_trace(go.Scattergl(
        x=series["timestamp"], y=series["pv_mw"], name="PV",
        fill="tozeroy", mode="lines",
        line=dict(color="#f5b301", width=1.2),
        fillcolor="rgba(245,179,1,0.25)",
    ))
    fig.add_trace(go.Scattergl(
        x=series["timestamp"], y=series["bess_mw"], name=t("BESS (+desc / −carga)", "BESS (+disch / −charge)"),
        mode="lines", line=dict(color="#17a2b8", width=1.4),
    ))
    fig.add_trace(go.Scattergl(
        x=series["timestamp"], y=series["poi_mw"], name=t("Potencia POI", "POI Power"),
        mode="lines", line=dict(color="#ff2e2e", width=2.2),
    ))
    fig.add_trace(go.Scattergl(
        x=series["timestamp"], y=series["soc_pct"], name="SoC",
        yaxis="y2", mode="lines", line=dict(color="#28a745", width=2),
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    xaxis = dict(title=t("Tiempo", "Time"), type="date")
    if x_range is not None:
        xaxis["range"] = list(x_range)
    fig.update_layout(
        template="plotly_white",
        xaxis=xaxis,
        yaxis=dict(title=t("Potencia (MW)", "Power (MW)")),
        yaxis2=dict(title="SoC (%)", overlaying="y", side="right", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, x=0.5, xanchor="center"),
        height=420, margin=dict(t=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Detalle por subelemento — estación meteorológica e inversores PV (Fase 7)
# ---------------------------------------------------------------------------

def _daily(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Submuestrea a media diaria para series largas (15 min × 1 año)."""
    if df is None or df.empty or "timestamp" not in df:
        return pd.DataFrame(columns=["timestamp", *cols])
    present = [c for c in cols if c in df.columns]
    out = (
        df[["timestamp", *present]]
        .set_index("timestamp")
        .resample("D")
        .mean()
        .reset_index()
    )
    return out


def chart_meteo_irradiance(pyranometers: pd.DataFrame) -> go.Figure:
    """Irradiancia de varios piranómetros redundantes (GHI y GPOA).

    ``pyranometers`` es la salida de ``build_meteo_pyranometers``: serie a
    resolución nativa (15 min) con ``ghi_clearsky``, ``ghi_p1..pN`` y
    ``gpoa_p1..pN``. Se dibujan todos los sensores: GHI (horizontal, naranjas) y
    GPOA (plano de módulos, azules), con el cielo claro como referencia.
    """
    fig = go.Figure()
    if pyranometers is None or pyranometers.empty:
        fig.update_layout(template="plotly_white", height=360)
        return fig
    x = pyranometers["timestamp"]
    ghi_cols = sorted(c for c in pyranometers.columns if c.startswith("ghi_p"))
    gpoa_cols = sorted(c for c in pyranometers.columns if c.startswith("gpoa_p"))

    if "ghi_clearsky" in pyranometers:
        fig.add_trace(go.Scattergl(
            x=x, y=pyranometers["ghi_clearsky"], name=t("GHI cielo claro", "GHI clear sky"),
            line=dict(color="#f5b301", width=1.2, dash="dot"),
            legendgroup="ref",
        ))
    ghi_palette = ["#e67e22", "#d35400", "#f39c12", "#e8590c", "#c0500a"]
    poa_palette = ["#2980b9", "#3498db", "#1f6f9c", "#5dade2", "#1a5276"]
    for i, col in enumerate(gpoa_cols):
        fig.add_trace(go.Scattergl(
            x=x, y=pyranometers[col], name=t(f"GPOA piranómetro {i + 1}", f"GPOA pyranometer {i + 1}"),
            line=dict(color=poa_palette[i % len(poa_palette)], width=1.6),
            legendgroup="gpoa",
        ))
    for i, col in enumerate(ghi_cols):
        fig.add_trace(go.Scattergl(
            x=x, y=pyranometers[col], name=t(f"GHI piranómetro {i + 1}", f"GHI pyranometer {i + 1}"),
            line=dict(color=ghi_palette[i % len(ghi_palette)], width=1.6),
            legendgroup="ghi",
        ))
    fig.update_layout(
        title=t("Irradiancia GHI y GPOA · piranómetros (resolución 15 min)", "GHI and GPOA irradiance · pyranometers (15-min resolution)"),
        template="plotly_white", yaxis_title="W/m²", height=360,
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, x=0.5, xanchor="center"),
        margin=dict(t=40),
    )
    return fig


def chart_meteo_ambient(meteo: pd.DataFrame) -> go.Figure:
    cols = [c for c in ("temp_ambient", "wind_speed", "humidity") if c in meteo.columns]
    serie = meteo[["timestamp", *cols]].sort_values("timestamp")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=serie["timestamp"], y=serie.get("temp_ambient"), name=t("Temp. ambiente", "Ambient temp."),
        line=dict(color="#fd7e14", width=2),
    ))
    fig.add_trace(go.Scattergl(
        x=serie["timestamp"], y=serie.get("wind_speed"), name=t("Viento", "Wind"),
        yaxis="y2", line=dict(color="#20c997", width=1.4),
    ))
    if "humidity" in serie:
        fig.add_trace(go.Scattergl(
            x=serie["timestamp"], y=serie["humidity"] * 100.0, name=t("Humedad", "Humidity"),
            yaxis="y2", line=dict(color="#3498db", width=1.2, dash="dot"),
        ))
    fig.update_layout(
        title=t("Temperatura, viento y humedad (resolución 15 min)", "Temperature, wind and humidity (15-min resolution)"),
        template="plotly_white",
        yaxis=dict(title="°C", side="left"),
        yaxis2=dict(title=t("m/s · %", "m/s · %"), overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center"),
        height=360, margin=dict(t=40),
    )
    return fig


def chart_pv_power(pv: pd.DataFrame) -> go.Figure:
    daily = _daily(pv, ["p_ac_mw", "p_dc_mw", "p_clipped_mw"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["timestamp"], y=daily.get("p_dc_mw"), name=t("Potencia DC", "DC Power"),
        line=dict(color="#f5b301", width=1.2, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=daily["timestamp"], y=daily.get("p_ac_mw"), name=t("Potencia AC", "AC Power"),
        line=dict(color="#e67e22", width=2), fill="tozeroy",
        fillcolor="rgba(230,126,34,0.15)",
    ))
    if "p_clipped_mw" in daily:
        fig.add_trace(go.Scatter(
            x=daily["timestamp"], y=daily["p_clipped_mw"], name=t("Clipping inversor", "Inverter clipping"),
            line=dict(color="#dc3545", width=1.2),
        ))
    fig.update_layout(
        title=t("Producción fotovoltaica (media diaria)", "Photovoltaic production (daily average)"),
        template="plotly_white", yaxis_title="MW", height=360,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center"),
        margin=dict(t=40),
    )
    return fig


def chart_pv_cell_temp(pv: pd.DataFrame) -> go.Figure:
    daily = _daily(pv, ["temp_cell", "poa"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["timestamp"], y=daily.get("poa"), name=t("Irradiancia POA", "POA irradiance"),
        yaxis="y2", line=dict(color="#f5b301", width=1.4),
    ))
    fig.add_trace(go.Scatter(
        x=daily["timestamp"], y=daily.get("temp_cell"), name=t("Temp. célula", "Cell temp."),
        line=dict(color="#fd7e14", width=2),
    ))
    fig.update_layout(
        title=t("Temperatura de célula e irradiancia POA (media diaria)", "Cell temperature and POA irradiance (daily average)"),
        template="plotly_white",
        yaxis=dict(title="°C", side="left"),
        yaxis2=dict(title="W/m²", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center"),
        height=360, margin=dict(t=40),
    )
    return fig


def chart_pcs_specific_power(series: pd.DataFrame) -> go.Figure:
    """Potencia específica (p.u.) de cada inversor PCS — una línea por unidad.

    Magnitud comparable entre inversores: potencia activa AC / potencia DC
    instalada. Se pintan las N series individuales (finas, translúcidas) más la
    media del grupo (línea destacada) para detectar inversores rezagados.
    """
    fig = go.Figure()
    if series is None or series.empty:
        return fig
    inverter_cols = [c for c in series.columns if c != "timestamp"]
    for col in inverter_cols:
        fig.add_trace(go.Scattergl(
            x=series["timestamp"], y=series[col], name=col,
            line=dict(color="#7f8fa6", width=0.8), opacity=0.35,
            showlegend=True, legendgroup="inversores",
            hovertemplate=f"{col}: %{{y:.3f}} p.u.<extra></extra>",
        ))
    group_mean = series[inverter_cols].mean(axis=1)
    fig.add_trace(go.Scattergl(
        x=series["timestamp"], y=group_mean, name=t("Media del grupo", "Group average"),
        line=dict(color="#1F4BFF", width=2.4), legendgroup="media",
        hovertemplate=t("Media", "Average") + ": %{y:.3f} p.u.<extra></extra>",
    ))
    fig.update_layout(
        title=t(
            f"Potencia específica por inversor (p.u. = AC / DC instalada) · "
            f"{len(inverter_cols)} inversores",
            f"Specific power per inverter (p.u. = AC / installed DC) · "
            f"{len(inverter_cols)} inverters",
        ),
        template="plotly_white", yaxis_title="p.u. (MW/MWp)", height=460,
        legend=dict(
            orientation="v", yanchor="top", y=1.0, x=1.02, xanchor="left",
            font=dict(size=10), itemsizing="constant",
            title=dict(text=t("Inversores (clic para aislar)", "Inverters (click to isolate)"), font=dict(size=11)),
        ),
        margin=dict(t=50, r=160),
    )
    return fig


def chart_bess_temperature(df: pd.DataFrame, temp_critical: float = 40.0) -> go.Figure:
    """Temperatura operativa del sistema BESS (media diaria) — detalle HVAC."""
    daily = _daily(df, ["temperature"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["timestamp"], y=daily.get("temperature"), name=t("Temperatura BESS", "BESS Temperature"),
        line=dict(color="#fd7e14", width=2),
    ))
    fig.add_hline(
        y=temp_critical, line_dash="dash", line_color="#d23f31",
        annotation_text=t(f"Crítico ({temp_critical:.0f} °C)", f"Critical ({temp_critical:.0f} °C)"),
    )
    fig.update_layout(
        title=t("Temperatura operativa del sistema (media diaria)", "System operating temperature (daily average)"),
        template="plotly_white", yaxis_title="°C", height=360,
        margin=dict(t=40),
    )
    return fig


def chart_hvac_cop_gauge(cop: float, target: float = 3.0) -> go.Figure:
    """Indicador tipo gauge del COP medio de enfriamiento (ideal > target)."""
    cop = float(cop)
    if cop >= target:
        bar = "#2fae5f"
    elif cop >= target - 0.3:
        bar = "#f1c40f"
    else:
        bar = "#e74c3c"
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(cop, 2),
        number={"valueformat": ".2f"},
        delta={"reference": target, "valueformat": ".2f"},
        title={"text": t(f"COP medio (ideal > {target:.1f})", f"Average COP (ideal > {target:.1f})")},
        gauge={
            "axis": {"range": [0, 5]},
            "bar": {"color": bar},
            "steps": [
                {"range": [0, target - 0.3], "color": "#fde2e0"},
                {"range": [target - 0.3, target], "color": "#fdf3d3"},
                {"range": [target, 5], "color": "#dcf3e6"},
            ],
            "threshold": {
                "line": {"color": "#1f2a37", "width": 3},
                "thickness": 0.75, "value": target,
            },
        },
    ))
    fig.update_layout(template="plotly_white", height=300, margin=dict(t=50, b=10))
    return fig


def chart_hvac_consumption(daily: pd.DataFrame) -> go.Figure:
    """Consumo HVAC diario (barras, MWh) con su % sobre el BESS (línea, eje 2)."""
    fig = go.Figure()
    if daily is None or daily.empty:
        fig.update_layout(template="plotly_white", height=360)
        return fig
    fig.add_trace(go.Bar(
        x=daily["timestamp"], y=daily["consumo_mwh"], name=t("Consumo HVAC", "HVAC consumption"),
        marker_color="#3b82f6", yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=daily["timestamp"], y=daily["pct_bess"], name=t("% del BESS", "% of BESS"),
        line=dict(color="#fd7e14", width=2), yaxis="y2",
    ))
    fig.update_layout(
        title=dict(text=t("Consumo energético HVAC (tendencia diaria)", "HVAC energy consumption (daily trend)"), y=0.97),
        template="plotly_white", height=360, margin=dict(t=70),
        yaxis=dict(title=t("MWh/día", "MWh/day")),
        yaxis2=dict(title=t("% del BESS", "% of BESS"), overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
    )
    return fig
