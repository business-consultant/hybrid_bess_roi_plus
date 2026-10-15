import streamlit as st
from bess_simulator.i18n import get_lang, t
from bess_simulator.ui.components.input_forms import render_input_forms
from bess_simulator.ui.components.kpi_cards import render_economic_kpis
from bess_simulator.ui.components.charts import (
    chart_yearly_income_costs, chart_soh_evolution, chart_cash_flow,
    chart_degradation_rte, chart_sensitivity_heatmap,
)
from bess_simulator.ui.components.recommendations_panel import render_recommendations
from bess_simulator.ui.components.alerts_panel import render_critical_events_shortcut
from bess_simulator.engine.simulation import run_simulation
from bess_simulator.engine.hybrid import compute_hybrid_economics
from bess_simulator.engine.sensitivity import run_sensitivity_matrix
from bess_simulator.recommendations import generate_full_recommendation
from bess_simulator.data.export import export_simulation_to_excel


def render_simulator_page():
    from bess_simulator.ui.components.sticky_header import render_sticky_header
    render_sticky_header("Simulador — Análisis de Sensibilidad")

    inputs = render_input_forms()

    if st.sidebar.button(t("Simular", "Simulate"), type="primary", use_container_width=True, help=t("Ejecuta la simulación con los parámetros actuales. Genera resultados a resolución de 15 minutos para toda la vida útil", "Runs the simulation with the current parameters. Generates results at 15-minute resolution for the entire useful life")):
        with st.spinner(t("Ejecutando simulación...", "Running simulation...")):
            cfg = st.session_state.get("app_config")
            results = run_simulation(inputs, seed=42, advanced_config=cfg)
            results.hybrid = compute_hybrid_economics(inputs, cfg or {}, seed=42, results=results)
            st.session_state["results"] = results
            st.session_state["inputs"] = inputs
            # Cálculos caros: se ejecutan UNA sola vez por simulación (no en
            # cada rerun). La matriz de sensibilidad lanza 35 simulaciones de
            # vida útil; el Excel serializa todas las hojas. Se cachean en
            # session_state y las pestañas solo los leen.
            st.session_state["sensitivity"] = run_sensitivity_matrix(
                inputs, seed=42, advanced_config=cfg,
            )
            st.session_state["excel_bytes"] = export_simulation_to_excel(inputs, results)
            # Coherencia: regenera el dataset del Dashboard Histórico BESS con el
            # escenario del operador y lo calibra a los años 1-2 del Simulador ROI.
            from bess_simulator.ui.views.data_generation import (
                rebuild_active_dataset_from_simulation,
            )
            rebuild_active_dataset_from_simulation()

    tab_sim, tab_dash = st.tabs([t("Simulador lifespan ROI", "Lifespan ROI simulator"), t("Dashboard Histórico BESS", "BESS Historical Dashboard")])
    with tab_sim:
        _render_simulator_tab(inputs)
    with tab_dash:
        from bess_simulator.ui.views.dashboard import render_dashboard_body
        render_dashboard_body()


def _render_simulator_tab(inputs):
    if "results" not in st.session_state:
        st.info(t("Configura los parámetros en el panel lateral y pulsa **Simular**.", "Configure the parameters in the side panel and click **Simulate**."))
        return

    results = st.session_state["results"]
    inputs = st.session_state["inputs"]

    render_economic_kpis(results, inputs)

    rec = generate_full_recommendation(inputs, results, advanced_config=st.session_state.get("app_config"), lang=get_lang())
    render_recommendations(rec)

    # Menciona los eventos críticos históricos del activo y enlaza con el registro
    # completo (Vista de planta) y el detalle del subelemento responsable.
    from bess_simulator.ui.views.data_generation import ensure_active_dataset
    bundle = ensure_active_dataset()
    render_critical_events_shortcut(bundle.get("df"), cfg=st.session_state.get("app_config"))

    tab1, tab2, tab3, tab4 = st.tabs([
        t("Ingresos/Costes", "Income/Costs"), "SoH", t("Cash Flow", "Cash Flow"), t("Degradación/RTE", "Degradation/RTE"),
    ])

    with tab1:
        st.plotly_chart(chart_yearly_income_costs(results.yearly_summary), use_container_width=True)
        st.caption(t("Comparación anual entre ingresos por venta de energía y costes operativos (OPEX)", "Annual comparison between energy sale revenue and operating costs (OPEX)"))
    with tab2:
        st.plotly_chart(chart_soh_evolution(results.yearly_summary, inputs.efficiency.soh_min), use_container_width=True)
        st.caption(t("Evolución del State of Health. La línea punteada indica el SoH mínimo garantizado", "State of Health evolution. The dotted line indicates the minimum guaranteed SoH"))
    with tab3:
        st.plotly_chart(chart_cash_flow(results.yearly_summary), use_container_width=True)
        st.caption(t("Flujo de caja acumulado descontado. Inicia en -CAPEX y crece con los ingresos netos", "Accumulated discounted cash flow. Starts at -CAPEX and grows with net income"))
    with tab4:
        st.plotly_chart(chart_degradation_rte(results.yearly_summary), use_container_width=True)
        st.caption(t("Degradación acumulada y eficiencia media por año. Tendencia descendente esperada", "Accumulated degradation and average efficiency per year. Downward trend expected"))

    st.subheader(t("Matriz de Sensibilidad", "Sensitivity Matrix"))
    sensitivity = st.session_state.get("sensitivity")
    if sensitivity is None:
        # Fallback: la simulación se cargó sin matriz (p. ej. sesión previa).
        # Se calcula una vez y se cachea para no repetirlo en cada rerun.
        with st.spinner(t("Calculando matriz de sensibilidad...", "Calculating sensitivity matrix...")):
            sensitivity = run_sensitivity_matrix(inputs, seed=42, advanced_config=st.session_state.get("app_config"))
            st.session_state["sensitivity"] = sensitivity
    st.caption(t(
        "Cada celda muestra el ROI resultante de variar OPEX (columnas) y precio de retribución (filas). La celda del caso base reproduce el ROI base.",
        "Each cell shows the resulting ROI from varying OPEX (columns) and retribution price (rows). The base-case cell reproduces the base ROI.",
    ))
    st.plotly_chart(chart_sensitivity_heatmap(sensitivity), use_container_width=True)

    st.divider()
    col_excel, col_save = st.columns(2)

    with col_excel:
        excel_bytes = st.session_state.get("excel_bytes")
        if excel_bytes is None:
            excel_bytes = export_simulation_to_excel(inputs, results)
            st.session_state["excel_bytes"] = excel_bytes
        st.download_button(
            label=t("Descargar resultados (Excel)", "Download results (Excel)"),
            data=excel_bytes,
            file_name="bess_simulation_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help=t("Descarga resultados en Excel: hoja de inputs, resumen anual y KPIs principales", "Download results in Excel: inputs sheet, annual summary and main KPIs"),
        )

    with col_save:
        sim_name = st.text_input(t("Nombre (opcional)", "Name (optional)"), key="sim_save_name", placeholder=t("Ej: Escenario base", "E.g.: Base scenario"))
        if st.button(t("Guardar simulación", "Save simulation"), type="secondary", use_container_width=True, help=t("Persiste los resultados en base de datos local para consulta y comparación posterior", "Persists the results in a local database for later review and comparison")):
            repo = st.session_state["sim_repo"]
            sens_repo = st.session_state["sens_repo"]
            sim_id = repo.save(inputs, results, name=sim_name or None, seed=42)
            sens_repo.save(sim_id, sensitivity)
            st.success(t(f"Simulación guardada: {sim_name or sim_id[:8]}", f"Simulation saved: {sim_name or sim_id[:8]}"))
