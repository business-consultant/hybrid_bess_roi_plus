# Resumen Técnico — Estado Actual de `hybrid_bess_roi_plus` en `feature/mejora_4_e1_plus`

**Documento:** Referencia para contexto técnico de continuación del desarrollo  
**Fecha:** 2026-08-28 (ver actualización de sesión del 2026-10-16 más abajo)  
**Rama:** `feature/mejora_4_e1_plus` (clonada desde `business-consultant/main`)  
**Stack:** Python 3.11+, Streamlit 1.30+, Plotly 5.18+, Pandas 2.0+, SQLite + Parquet

---

## 0. Actualización de sesión — 2026-10-16

**Contexto de la sesión:** se pidió añadir un selector de idioma (ES/EN) a la app. Durante
el trabajo se descubrió que existían **dos clones locales independientes** del mismo repo
de GitHub (`business-consultant/hybrid_bess_roi_plus`), sin ninguna relación vía git entre
sí (ambos apuntaban al único commit del repo, `2a01563`):

- **`C:\Users\jlsilva\repos\hybrid_bess_roi_plus`** (esta carpeta, sin sufijo) — copia de
  trabajo canónica: tiene `.venv` propio y es la que `run_dev.bat` sirve en
  `localhost:8502`. Aquí vivía ya, sin commitear, el trabajo de "Mejora_4" (telemetría +
  Trending Charts).
- **`hybrid_bess_roi_plus_lee`** — un clon aislado creado automáticamente para una sesión
  de trabajo con el asistente (rama local `feature/mejora_4_e1_plus`, que **no existía en
  GitHub**). Ahí se hizo todo el trabajo de i18n antes de detectar la duplicidad. Esa
  carpeta ya no es necesaria y puede borrarse si reaparece — está añadida a `.gitignore`
  por si se crea anidada dentro de esta carpeta otra vez.

**Resolución:** todo el trabajo (Mejora_4 + i18n) se fusionó y se comiteó aquí, en esta
carpeta canónica, en la rama `feature/mejora_4_e1_plus`, que ahora **sí existe en GitHub**
(`git push -u origin feature/mejora_4_e1_plus`). Commits de esta sesión:

1. `c887cbf` — Añade el catálogo de telemetría BESS (`data/telemetry.py`) y la vista
   **Trending Charts** (`ui/views/trending_charts.py`), con su entrada de menú en `app.py`.
2. `19d1a93` — Añade el **selector de idioma ES/EN** (`src/bess_simulator/i18n.py`, helper
   `t(es, en)`) en el sidebar, con persistencia solo de sesión (`st.session_state`).
   Traduce toda la UI estática (8 páginas, componentes, gráficos Plotly) y el texto
   generado dinámicamente por el motor de recomendaciones (`recommendations/`), con
   español como idioma por defecto (los tests existentes no se tocaron y siguen en
   español). Las claves internas (nombres de página en `session_state`, categorías de
   alarma CATEGORY_*, nombres de subelementos como "Módulos BESS") se mantuvieron en
   español a propósito, porque se usan como identificadores en varios sitios del código,
   no como texto de cara al usuario.
3. `64c804f` — Ignora la carpeta anidada `hybrid_bess_roi_plus_lee/` en `.gitignore`.

**Limitación conocida:** las tablas de detalle por subelemento en "Elementos de Planta"
(BMS/PCS, generadas en `engine/elements.py`) mantienen sus encabezados de columna en
español en ambos idiomas — no se tradujeron para no arriesgar romper el código que las
referencia por nombre de columna.

**Lección para el futuro:** si un cambio de código "no se ve" en la app corriendo, antes
de nada comprobar qué proceso sirve realmente el puerto (`netstat -ano` +
`Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" | Select CommandLine`), porque
puede haber más de una copia local del repo activa a la vez.

---

## 1. Objetivo del Proyecto y "Mejora_4"

### 1.1 Propósito del proyecto (hybrid_bess_roi_plus)

Herramienta empresarial de **análisis de sensibilidad económica** para plantas híbridas **PV + BESS (Battery Energy Storage System)**. Simula el retorno de inversión a nivel de 15 minutos durante toda la vida útil del activo (10–25 años), visualiza indicadores técnico-económicos y genera recomendaciones automáticas basadas en umbrales de negocio.

**Casos de uso:**
- Evaluación de viabilidad económica de inversiones en almacenamiento
- Optimización de despacho de energía (arbitraje, servicios de red, curtailment)
- Análisis de sensibilidad CAPEX-Precio-Ciclos
- Seguimiento de degradación de batería a lo largo de vida útil
- Validación de confiabilidad de sistemas híbridos (coherencia PV↔BESS↔POI)

### 1.2 ¿Qué es "Mejora_4"?

**Nombre:** `feature/mejora_4_e1_plus`  
**Objetivo:** Introducir visibilidad operativa de señales BESS híbridas mediante:

1. **Catálogo exhaustivo de 68 señales BESS** (documento `prompts_hybrid_BESS.md`):
   - 13 elementos del sistema (BMS, BBANK, PCS, BCTRL, BTMS, FPS, UPS, CT, ANL, EMS, etc.)
   - 48+ señales nuevas + 20 preexistentes (operación BESS, meteorología, generación PV)
   - Especificación completa de generación sintética para pruebas SCADA

2. **Módulo "Trending Charts"** (nueva página UI en Streamlit):
   - Visualización simultánea de hasta 12 señales en el mismo eje temporal (15 min)
   - Soporte de **eje Y secundario** para señales con unidades incompatibles
   - Validación de coherencia entre preexistentes (meteo, PV) y nuevas (BESS ops)
   - Selección granular de plantas, señales y resoluciones de agregación

3. **Generador sintético de datos telemetría** (`telemetry.py`):
   - Derivación on-demand de señales BESS (curvas OCV, pérdidas I²R, derating, contadores)
   - Integración con capas preexistentes (meteorología, PV, operación)
   - Validación física de invariantes (MaxTemp ≥ AvgTemp ≥ MinTemp, SOC ∈ [5–95], monotonicidad de SOH, etc.)

**Beneficio:** Preparar el simulador para integración futura con SCADA real manteniendo validación exhaustiva de consistencia física sin necesidad de hardware.

---

## 2. Estructura del Repositorio

### 2.1 Árbol de carpetas

```
hybrid_bess_roi_plus/
├── pyproject.toml                # Metadatos, dependencias, pytest config
├── README.md                      # Instrucciones arranque / punto estable
├── run_dev.bat                    # Script Windows para entorno + Streamlit
│
├── src/bess_simulator/            # Núcleo de la aplicación
│   ├── __init__.py
│   ├── config.py                  # Constantes, rangos, valores por defecto
│   │                              # CALENDAR_AGING_RATE, RTE_ANNUAL_DECAY, umbrales
│   │
│   ├── models/                    # Dataclasses de dominio (input/output)
│   │   ├── parameters.py          # SimulationInputs + 4 sub-dataclasses
│   │   │                          # (EconomicParams, BessParams, EfficiencyParams, ActivityParams)
│   │   ├── results.py             # SimulationResults, SensitivityResult
│   │   └── topology.py            # Metadatos de topología (POI limit, C-rate, etc.)
│   │
│   ├── engine/                    # Motor de cálculo principal
│   │   ├── simulation.py          # run_simulation() — genera arrays 15 min
│   │   ├── sensitivity.py         # run_sensitivity_matrix() — CAPEX × Precio
│   │   ├── hybrid.py              # compute_hybrid_economics() — reconciliación PV↔BESS
│   │   ├── plant.py               # plant_lifecycle() — series fotovoltaica + BESS despacho
│   │   ├── elements.py            # Funciones helpers: curva OCV, derating, degradación
│   │   └── validation.py          # Validación de parámetros contra rangos
│   │
│   ├── data/                      # Generación y exportación de datos
│   │   ├── synthetic.py           # generate_dashboard_dataset() — 15 min sintético
│   │   ├── meteo.py               # Perfil meteorológico (GHI, DNI, T_amb, etc.)
│   │   ├── pv.py                  # Planta fotovoltaica (POA irr, eficiencia, T_cell)
│   │   ├── export.py              # Export a Excel/CSV
│   │   ├── telemetry.py  [NUEVA]  # SIGNAL_CATALOG + build_signal_series()
│   │   └── __init__.py
│   │
│   ├── recommendations/           # Motor de recomendaciones automáticas
│   │   ├── __init__.py            # generate_full_recommendation()
│   │   ├── decision_tree.py       # Evaluación ROI + Degradación
│   │   ├── sub_recommendations.py # 5 recomendaciones por parámetro
│   │   ├── alarms.py              # Alarmas de valores fuera de rango
│   │   └── colors.py              # Mapas color ←→ recomendación
│   │
│   ├── storage/                   # Capa de persistencia
│   │   ├── paths.py               # Resolución de rutas (dev vs instalador)
│   │   ├── schema.py              # Esquema SQLite (5 tablas) + init_db()
│   │   ├── repositories.py        # Acceso a CRUD (simulaciones, dashboard, sensibilidad)
│   │   ├── app_config.py          # load_config / save_config (~50 parámetros)
│   │   ├── analytics.py           # Consultas DuckDB sobre Parquet histórico
│   │   └── __init__.py
│   │
│   └── ui/                        # Interfaz Streamlit (5 páginas + componentes)
│       ├── app.py                 # Entry point: init_db + sidebar navegación
│       ├── components/            # Reutilizables
│       │   ├── charts.py          # 11 funciones gráficos Plotly
│       │   ├── input_forms.py     # Formularios sidebar (18 parámetros)
│       │   ├── kpi_cards.py       # Tarjetas ROI y VAN
│       │   ├── recommendations_panel.py # Visualización recomendaciones
│       │   ├── alerts_panel.py    # Visualización alarmas
│       │   ├── sticky_header.py   # Cabecera fija página
│       │   └── __init__.py
│       └── views/                 # Páginas (rutas)
│           ├── simulator.py       # Módulo 1: Simulador BESS
│           ├── dashboard.py       # Módulo 2: Dashboard Histórico
│           ├── hybrid_plant.py    # Módulo 3: Planta Híbrida (topología + despacho)
│           ├── saved_simulations.py # Módulo 4: Simulaciones Guardadas
│           ├── trending_charts.py [NUEVA] # Módulo 5: Gráficos de Tendencia
│           ├── methodology.py     # Módulo 6: Metodología
│           ├── monitoring.py      # Módulo 7: Monitoreo (no lista sidebar aún)
│           ├── settings.py        # Módulo 8: Configuración Avanzada
│           ├── data_generation.py # Utilidad: generar dataset sintético
│           └── __init__.py
│
├── tests/                         # Suite de tests (pytest)
│   ├── test_simulation.py         # run_simulation() casos base
│   ├── test_hybrid.py             # Reconciliación PV↔BESS
│   ├── test_plant.py              # Curvas PV, BESS despacho
│   ├── test_sensitivity.py        # Matriz sensibilidad
│   ├── test_recommendations.py    # Motor recomendaciones
│   ├── test_alarms.py             # Alarmas físicas
│   ├── test_elements.py           # Helpers (OCV, degradación)
│   ├── test_meteo.py              # Perfiles meteorológicos
│   ├── test_pv.py                 # Curvas fotovoltaicas
│   ├── test_synthetic_v2.py       # Generación sintética
│   ├── test_storage.py            # CRUD + persistencia
│   ├── test_telemetry.py [NUEVA]  # Catálogo signals + validación física
│   ├── test_data/                 # Fixtures (JSON, CSV)
│   │   └── excel_reference.json   # Referencia Excel
│   └── __init__.py
│
├── docs/                          # Documentación funcional (Markdown)
│   ├── notas.md                   # Notas sueltas
│   │
│   ├── 01-analysis/               # Análisis de requisitos iniciales
│   │   ├── modulo 1/              # Árbol decisiones BESS, parámetros simulador
│   │   └── modulo 2/              # Notas módulo 2
│   │
│   └── 02-design/                 # Documentación de diseño (DEFINITIVA)
│       ├── arquitectura-general.md      # Stack tecnológico, diagrama capas
│       ├── modelo-datos.md              # Dataclasses y diagramas mermaid
│       ├── modulos-funcionales.md       # Especificación por página (18 parámetros, etc)
│       ├── balance-hibrido-pv-bess.md   # Reconciliación económica PV↔BESS
│       ├── estrategias-despacho.md      # Arbitraje, secundaria, energy shifting
│       ├── motor-recomendaciones.md     # Lógica evaluación y redacción
│       ├── umbrales-garantia-y-alertas.md # Alarmas físicas
│       ├── empaquetado-distribucion.md # Instalador (innosetup)
│       ├── guia-desarrollo.md           # Contribución, testing, debugging
│       ├── guia-recuperacion-contexto.md # Cómo recuperar estado
│       ├── prompts_hybrid_BESS.md [NUEVA] # Especificación 68 señales + reglas físicas
│       └── notas.md
│
├── installer/                     # Distribuición (Windows)
│   ├── bess_installer.iss         # Innosetup script
│   ├── launch_bess.bat            # Launcher post-install
│   ├── requirements.txt           # Pines pip para instalador
│   └── build_package.py           # Script build
│
└── .gitignore
```

### 2.2 Módulos clave por funcionalidad

| Funcionalidad | Archivos clave | Descripción |
|---|---|---|
| **Simulación ROI** | `engine/simulation.py`, `models/parameters.py` | 18 parámetros → arrays 15 min durante vida útil |
| **Reconciliación híbrida** | `engine/hybrid.py`, `storage/app_config.py` | PV→BESS coste cero, crédito sinergia, curtailment |
| **Despacho BESS** | `engine/plant.py`, `docs/estrategias-despacho.md` | Arbitraje, secundaria, energy shifting, multiservicio |
| **Degradación** | `engine/elements.py`, `config.py` | Calendario + cíclico, DOD, temperatura |
| **Catálogo de señales** | `data/telemetry.py`, `docs/prompts_hybrid_BESS.md` | 68 señales BESS, generación sintética, validación |
| **Trending Charts** | `ui/views/trending_charts.py` | Multi-señal, eje secundario, coherencia |
| **Recomendaciones** | `recommendations/`, `storage/app_config.py` | ROI vs capital, degradación, parámetros críticos |
| **Persistencia** | `storage/`, `models/results.py` | SQLite (meta) + Parquet (series) + DuckDB (analítica) |
| **UI** | `ui/app.py`, `ui/views/`, `ui/components/` | 8 páginas, componentes reutilizables |

---

## 3. Datos: Inputs y Orígenes

### 3.1 Entrada de simulación (18 parámetros + 4 derivados)

| Categoría | Parámetro | Tipo | Rango | Descripción |
|---|---|---|---|---|
| **Económicos** | CAPEX (€/MW) | number | 300 K – 1 M | Inversión inicial por megavatio |
| | OPEX (€/MW/año) | number | 11 K – 22.5 K | Operación y mantenimiento anual |
| | Tasa descuento (%) | slider | 5 – 10 | WACC financiero |
| | Spread medio (€/MWh) | slider | 20 – 100 | Diferencia precio venta–carga |
| **Batería** | Potencia (MW) | number | 1 – 200 | Potencia nominal AC |
| | 1/C-Rate (MWh/MW) | slider | 1 – 8 | Relación energía/potencia |
| | Ciclos vida útil | number | 6 K – 8 K | Ciclos garantía a 80% SoH |
| | Vida útil (años) | slider | 10 – 25 | Período análisis económico |
| **Eficiencia** | SoH inicial (%) | slider | 95 – 100 | Salud celda inicial |
| | RTE (%) | slider | 80 – 90 | Rendimiento redondo (round-trip efficiency) |
| | Degradación (%/ciclo) | select | 0.005 – 0.020 | Pérdida cíclica por ciclo |
| | SoH mínimo (%) | slider | 70 – 80 | Límite operacional garantizado |
| | DoD máximo (%) | slider | 80 – 95 | Profundidad descarga permitida |
| **Actividad** | Ciclos anuales | slider | 300 – 1 K | Ciclos esperados/año |
| **Derivados** | Capacidad (MWh) | read-only | — | Potencia × C-Rate × SoH |
| | CAPEX total (€) | read-only | — | CAPEX/MW × Potencia |
| | OPEX anual (€) | read-only | — | OPEX/MW/año × Potencia |

### 3.2 Datos operacionales (sintéticos, 15 minutos)

**Orígenes:**
1. **Perfil OMIE histórico + futuro** (`data/synthetic.py`):
   - Precios horarios pool español (o simulados)
   - Resolución 1 hora → interpolar a 15 min
   - Patrón estacional y volatilidad

2. **Meteorología** (`data/meteo.py`):
   - GHI (Global Horizontal Irradiance) en W/m²
   - DNI (Direct Normal Irradiance) en W/m²
   - Temperatura ambiente en °C
   - Resolución 15 min
   - Patrón diario + estacional

3. **Generación PV** (`data/pv.py`):
   - Irradiancia POA (Plane-of-Array) derivada de GHI/DNI
   - Temperatura de celda (ambiente + efecto I²h)
   - Potencia AC: POA × eficiencia(T) → DC → AC (con pérdidas)
   - Resolución 15 min
   - Límite POI: 50 MW (curtailment cuando se supera)

4. **Despacho BESS** (`engine/plant.py`):
   - Consigna diaria (arbitraje, secundaria, energy shifting, multiservicio)
   - Respeta límites: SoC [5–95%], DoD, potencia, corriente
   - Descarga concentrada 20–24h (sin solapamiento solar)
   - Resolución 15 min

5. **Catálogo telemetría** (`data/telemetry.py` **NUEVA**):
   - 13 elementos BESS (BMS, BBANK, PCS, BCTRL, BTMS, FPS, UPS, CT, ANL, EMS)
   - 68 señales totales (16 BMS + 6 BBANK + 13 PCS + 5 BCTRL + 7 BTMS + 5 FPS + 1 UPS + 1 CT + 2 ANL + 5 EMS)
   - Derivación on-demand a partir de síntesis (no precalculada)
   - Validación física: MaxT ≥ AvgT ≥ MinT, SOC ∈ [0, 100], SOH monotónico, contadores crescentes, P=V×I

**Archivos de datos persistentes:**
- SQLite `bess.db`: Metadatos de simulaciones, KPIs guardadas, configuración
- Parquet `data/parquet/`: Series históricas de 15 min (comprimido columnar)
- Excel exports: Resumen económico, gráficos, matriz sensibilidad

---

## 4. Modelo de ROI y Supuestos Económicos

### 4.1 Flujos de valor capturados

| Servicio | Mecanismo | Ingresos | Duración | Parámetro config |
|---|---|---|---|---|
| **Arbitraje** | Carga valle nocturno (precio bajo) → descarga pico (precio alto) | Spread × Energía anual | Todos años | `avg_spread_price` |
| **Servicios de red (Secundaria aFRR)** | Modulación banda ±0.15 MW en 12–18h | Ingresos capacidad aFRR | Opcional, no en base | `advanced_config` |
| **Energy Shifting PV** | Captura excedentes FV mediodía → venta atardecer/noche | Spread × Energía PV→BESS | Todos años | Hybrid ROI credit |
| **Reducción curtailment** | Absorbe excedentes solar que no caben en POI | Ingresos evitados en recorte | Estimado como "crédito" | `curtailment_factor` |

### 4.2 Supuestos económicos (codificados o configurables)

| Concepto | Valor por defecto | Configurabilidad | Efecto |
|---|---|---|---|
| **CAPEX** | 400–600 K€/MW | Input usuario (sidebar) | Inversión inicial (NPV negativo año 0) |
| **OPEX** | 15 K€/MW/año | Input usuario | Coste anual perpetuo (descuento tiempo) |
| **Tasa descuento (r)** | 7% | Input usuario (5–10%) | DCF anualizado y VAN |
| **Vida útil** | 15 años (default) | Input usuario (10–25) | Horizonte de análisis |
| **Precio carga grid** | 35 €/MWh | `bess_grid_charge_price` | Crédito PV→BESS (sinergia) |
| **Degradación calendario** | ~0.5%/año | `CALENDAR_AGING_RATE` | SoH anual lineal |
| **Degradación cíclica** | 0.005–0.02 %/ciclo | Input usuario | SoH función ciclos acumulados |
| **RTE (redondo)** | 85% | Input usuario (80–90%) | Pérdidas ciclo carga–descarga |
| **SoH mínimo garantizado** | 80% | Input usuario (70–80%) | Ciclos vida útil hasta límite |
| **Inflación** | 2% (fijo) | `inflation_rate` | Escalado OPEX futuro |

### 4.3 Fórmulas clave

#### ROI Anualizado

$$\text{ROI}_{\text{anual}} = \left( 1 + \frac{\text{DCF}_{\text{acumulado, final}}}{|\text{CAPEX}|} \right)^{1/\text{vida\_útil}} - 1$$

Comparable directo con tasa descuento para decisión inversión.

#### VAN (incluye -CAPEX año 0)

$$\text{VAN} = -\text{CAPEX} + \sum_{t=1}^{N} \frac{\text{CashFlow}_t}{(1+r)^t}$$

donde $\text{CashFlow}_t = \text{Ingresos}_t - \text{OPEX}_t - \text{Tax}_t$

#### Capacidad efectiva en año t

$$C_t = C_0 \times \left( 1 - \text{Degradación}_{\text{calendario}, t} - \text{Degradación}_{\text{cíclica}, t} \right)$$

con:
- Degradación calendario: $\approx 0.5\%/\text{año}$
- Degradación cíclica: $\sum_{d=1}^{t \times 365} (\text{ciclos}\_d \times \text{deg\_ciclo}\_\%)$

#### Energía anual y spread

$$E_{\text{anual}} = C_t \times \text{ciclos}_{\text{anuales}} \times \text{DoD} \times \text{RTE}$$

$$\text{Spread}_{\text{efectivo}} = \text{Spread}_{\text{base}} + \frac{E_{\text{PV→BESS}} \times P_{\text{carga}}}{E_{\text{descarga}}}$$

(El crédito de sinergia PV→BESS se suma al VAN de planta.)

#### Sensibilidad: matriz CAPEX × Precio

Calcula ROI para combinación $N \times M$ de:
- CAPEX: [300 K, 400 K, 500 K, 600 K, 700 K, 800 K, 900 K, 1000 K] €/MW
- Precio spread: [20, 30, 40, 50, 60, 70, 80, 90, 100] €/MWh

Heatmap Plotly interactivo en UI.

### 4.4 Validaciones y rangos críticos

| Validación | Regla | Impacto |
|---|---|---|
| **SoC operacional** | 5% ≤ SoC ≤ 95% | Excluir extremos que aceleren degradación |
| **DoD máximo** | Descarga máxima ≤ DoD_config (80–95%) | Respetar garantía batería |
| **SoH mínimo garantizado** | SoH > SoH_min (70–80%) | Fin vida útil cuando se cruza |
| **Potencia/Corriente** | Respetar límites descarga/carga | Activar derating térmico |
| **RTE mínimo** | 80% ≤ RTE ≤ 90% | Coherencia física |

---

## 5. Estado Actual: Qué está hecho, a medias y pendiente

### 5.1 Estado funcional por componente

#### ✅ **Completado y verificado**

| Módulo | Status | Detalles |
|---|---|---|
| **Simulación ROI (engine/simulation.py)** | ✅ Completo | Arrays 15 min, flujos caja, DCF, VAN, degradación |
| **Reconciliación PV↔BESS (engine/hybrid.py)** | ✅ Completo | Coste cero carga solar, crédito sinergia, curtailment estimado |
| **Despacho BESS (engine/plant.py)** | ✅ Completo | 4 estrategias (arbitraje, aFRR, energy shifting, multiservicio), respeta POI |
| **Sensibilidad (engine/sensitivity.py)** | ✅ Completo | Matriz CAPEX × Precio, heatmap interactivo |
| **Modelo físico (engine/elements.py)** | ✅ Completo | OCV(SOC), IR drop, derating, degradación calendario+cíclica |
| **Recomendaciones (recommendations/)** | ✅ Completo | ROI + Degradación, 5 sub-recomendaciones, alarmas físicas |
| **UI Módulos 1–4** | ✅ Completo | Simulador, Dashboard, Guardadas, Metodología |
| **Persistencia (storage/)** | ✅ Completo | SQLite (meta) + Parquet (series) + DuckDB (analítica) |
| **Tests suite** | ✅ 95/95 passing | Regression coverage completa |

#### 🟡 **En progreso / "Mejora_4"**

| Módulo | Status | Detalles |
|---|---|---|
| **Trending Charts (ui/views/trending_charts.py)** | 🟢 **NUEVO** | Multi-señal (12 máx), eje secundario, agregación por granularidad, validación unidades |
| **Catálogo telemetría (data/telemetry.py)** | 🟢 **NUEVO** | 68 señales BESS, 13 elementos, generación on-demand, validación física |
| **Tests telemetría (test_telemetry.py)** | 🟢 **NUEVO** | 3 tests: signals generate, invariants preserved, preexisting layers selectable |
| **Especificación prompts (docs/prompts_hybrid_BESS.md)** | 🟢 **NUEVO** | 154 líneas, 68 señales con prompt implementación, reglas físicas, validación |
| **App routing (ui/app.py)** | 🟡 Minor | Añadido "Trending Charts" a sidebar, routing OK |

#### ⏳ **Pendiente / No iniciado**

| Funcionalidad | Razón | Impacto |
|---|---|---|
| **Integración SCADA real** | No hay hardware BESS disponible en entorno prueba | Generador sintético cubre pruebas, pero sin datos reales |
| **Monitoreo en tiempo real** | Módulo skeleton existe (monitoring.py) pero no completado | UI necesita conexión MQTT/OPC-UA a SCADA |
| **Alertas persistentes** | Alarmas se calculan pero no se archivan en base datos | Sin histórico de eventos para auditoría |
| **Exportación SCADA estándar** | XML/JSON para sistemas de terceros no implementado | Output actual: Excel + CSV |
| **Autenticación de usuarios** | Streamlit sin sesiones; no hay multi-usuario | Todos comparten misma base datos bess.db |
| **Versionado de parámetros avanzados** | Config se guarda pero sin histórico de cambios | No se puede auditar quién/cuándo cambió umbrales |
| **Profiling energético horario** | Dashboard muestra promedio diario; desglose hora no disponible | Imposible ver picos de carga 00–05h vs descarga 20–24h en detalle |
| **Integración con EMS real** | Motor recomendaciones genera sugerencias pero sin API feedback | Círculo cerrado: simulación aislada de operación |

### 5.2 Últimos checkpoints verificados

**Commit estable de referencia:** `70d2983a62b9e6cd285473c779aac2214c497a52` (2026-06-17)
- Mensaje: "Reconciliacion hibrida PV->BESS y mejoras de rendimiento UI"
- Estado: ✅ Todos tests pasen (95/95)
- Archivos de diseño finalizados

**Cambios posteriores (operacionales, 2026-07-07 → 2026-08-28):**
- ✅ Optimización estrategias despacho (curtailment 50 MW, descarga 20–24h)
- ✅ Especificación completa de 68 señales telemetría
- ✅ Trending Charts e implementación telemetry.py
- ✅ Tests telemetría (3/3 passing)
- ✅ Documentación prompts_hybrid_BESS.md

### 5.3 TODOs y Issues conocidos

#### **Bloqueadores potenciales**

| Issue | Severidad | Workaround | Responsable |
|---|---|---|---|
| **Escalado a múltiples plantas en UI** | Media | Dataset fixture soporta múltiples plantas pero UI muestra una. Refactorizar `trending_charts.py` selectbox | `feature/mejora_4_e1_plus` owner |
| **Caché Streamlit y hot-reload** | Media | Matar terminal + reiniciar Streamlit tras cambios grandes | Dev (conocido) |
| **Excel export lento (>10 años × 365 días)** | Baja | Implementar on-demand con progress bar | Roadmap |

#### **Mejoras futuras no críticas**

- [ ] Dashboard profiling horario (picos 00–05h, 20–24h desglosados)
- [ ] Sincronización SCADA en tiempo real (requiere OPC-UA/MQTT server)
- [ ] Autenticación multi-usuario con roles (Streamlit Community no soporta nativo)
- [ ] API REST para terceros (FastAPI wrapper)
- [ ] Alertas persistentes con auditoría de eventos

---

## 6. Stack Tecnológico y Dependencias

### 6.1 Versiones fijadas (pyproject.toml)

```toml
[project]
name = "bess-simulator"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "streamlit>=1.30",          # UI web interactiva
    "pandas>=2.0",              # DataFrames 15-min
    "numpy>=1.24",              # Cálculo vectorizado
    "plotly>=5.18",             # Gráficos interactivos (Scattergl, Heatmap)
    "openpyxl>=3.1",            # Export Excel
    "pyarrow>=14.0",            # Parquet columnar comprimido
    "duckdb>=0.10",             # SQL sobre Parquet (analítica)
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",              # Testing framework
]
```

### 6.2 Estructura de memoria y rendimiento

| Operación | Tiempo típico | Resolución | Memoria |
|---|---|---|---|
| `run_simulation()` (15 años, 525 600 intervalos) | ~2–3 s | 15 min | ~50 MB |
| `run_sensitivity_matrix()` (8×9 CAPEX×Precio) | ~5–7 s (paralelo) | Por punto | ~30 MB acum. |
| `build_signal_series()` (1 señal, 15 min/año) | ~200 ms | 15 min | ~2 MB |
| Gráfico Plotly Scattergl (5 K puntos) | <500 ms render | 15 min | ~10 MB JS |
| Export Excel (résumé + gráficos) | ~1–2 s | Anual | ~5 MB file |
| SQL DuckDB sobre Parquet (anual) | <100 ms | — | ~1 MB query |

**Flags Streamlit en run_dev.bat:**
```powershell
--server.headless true       # Modo no interactivo
--server.runOnSave false     # Evitar recargas accidentales
--logger.level=info          # Logging estándar
```

### 6.3 Dependencias externas y limitaciones

| Herramienta | Versión | Uso | Limitación |
|---|---|---|---|
| **Python** | 3.11+ | Core | Requiere .venv local, no integrado sistema |
| **Streamlit** | 1.30+ | UI | Sesiones no persistentes (reload cada interacción) |
| **Plotly** | 5.18+ | Gráficos | Descarga JS desde CDN (offline requiere config) |
| **Pandas** | 2.0+ | DataFrames | No distribuido; límite ~4 GB RAM por máquina |
| **DuckDB** | 0.10+ | Analítica SQL | Solo consultas, no escritura concurrente |
| **SQLite** | stdlib | Persistencia | Mono-escritura; no apta clusters |
| **Innosetup** | 6.x | Instalador Windows | Solo Windows; Linux requiere distribución alternativa |

### 6.4 Arquitectura de capas (visual)

```
┌─────────────────────────────────────────────────────────┐
│ Interfaz: Streamlit (5 páginas + sidebar)               │
├─────────────────────────────────────────────────────────┤
│ Componentes: Gráficos (Plotly), Formularios, Cards      │
├─────────────────────────────────────────────────────────┤
│ Lógica: Simulación, Recomendaciones, Telemetría       │
├─────────────────────────────────────────────────────────┤
│ Motor: Física (OCV, RTE, degradación), Despacho        │
├─────────────────────────────────────────────────────────┤
│ Datos: Sintéticos (PV, meteo, BESS), Catálogo signals │
├─────────────────────────────────────────────────────────┤
│ Persistencia: SQLite (meta) + Parquet (series)         │
├─────────────────────────────────────────────────────────┤
│ Almacenamiento: Filesystem local (/data/parquet/, DB)  │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Recomendaciones para Continuación

### 7.1 Orientación para trabajar en `feature/mejora_4_e1_plus`

**Flujo de desarrollo sugerido:**

1. **Setup local:**
   ```powershell
   cd C:\Users\jlsilva\repos\hybrid_bess_roi_plus_lee
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   python -m pytest tests/ -v           # Verificar tests pasen
   python -m streamlit run src/bess_simulator/ui/app.py
   ```

2. **Familiarización con rama:**
   - Leer [docs/02-design/balance-hibrido-pv-bess.md](docs/02-design/balance-hibrido-pv-bess.md) (reconciliación PV↔BESS)
   - Ejecutar simulación de ejemplo en UI y verificar trending charts
   - Inspeccionar [src/bess_simulator/data/telemetry.py](src/bess_simulator/data/telemetry.py) para entender catálogo de 68 señales
   - Revisar tests en [tests/test_telemetry.py](tests/test_telemetry.py)

3. **Cambios recomendados a continuación:**

   a) **Persistencia de señales** (Parámetro "Guardar")
      - Trending Charts actualmente no guarda series en Parquet
      - Modificar `repositories.py` para StorageRepository.save_signal_series(plant, element, signal, df)
      - Habilitar replay histórico de trending

   b) **Alertas inteligentes por señal**
      - Detectar desviaciones de patterns (ej: SOC no converge a 50%, MaxTemp > 50°C sostenido)
      - Integrar con panel alarmas existente
      - Archivo: `recommendations/alarms.py` + `ui/components/alerts_panel.py`

   c) **Profiling horario en dashboard**
      - Desglose de ciclos (carga 00–05h vs descarga 20–24h) en histogramas
      - Mapa de calor potencia × hora
      - Permitir zoom a subventanas temporales

   d) **API REST (roadmap)**
      - Wrapper FastAPI para consultas de simulación sin UI
      - Endpoint `POST /simulate` → JSON resultados
      - Útil para integración EMS

### 7.2 Puntos de entrada por interés

| Interés | Archivo(s) clave | Acción recomendada |
|---|---|---|
| **Mejorar gráficos / UX** | `ui/views/trending_charts.py`, `ui/components/charts.py` | Añadir filtros de tiempo, export gráficos PNG, selección por categoría |
| **Extender catálogo de señales** | `data/telemetry.py`, `docs/prompts_hybrid_BESS.md` | Añadir nuevos elementos (Grid aggregation, MPPT, etc.), derivaciones complejas |
| **Precisar modelo físico** | `engine/elements.py`, `engine/simulation.py` | Incluir hysteresis térmica, curvas OCV reales LFP, dinámica PCS |
| **Mejorar recomendaciones** | `recommendations/decision_tree.py`, `storage/app_config.py` | Lógica fuzzy o ML ligero para riesgos no-lineales |
| **Análisis histórico** | `storage/analytics.py`, `ui/views/dashboard.py` | Implementar regresiones temporales, detección anomalías en Parquet |
| **Instalador / Packaging** | `installer/`, `installer/build_package.py` | Actualizar a NSIS o WiX; soportar desinstalador limpio |

### 7.3 Verificaciones antes de Push a Main

Cuando completar una mejora en `feature/mejora_4_e1_plus`:

```powershell
# 1. Tests
python -m pytest tests/ -v --tb=short
# Esperado: 95+ passing (no regresión)

# 2. Linting (opcional pero recomendado)
python -m pylint src/bess_simulator/ --disable=C0111 --max-line-length=100

# 3. UI check
python -m streamlit run src/bess_simulator/ui/app.py
# Visitar http://localhost:8501, verificar trending charts y recomendaciones

# 4. Datos consistency
# Ejecutar simulación de ejemplo, verificar trending charts muestran coherencia

# 5. Commit y push
git add .
git commit -m "Descripción concisa"
git push origin feature/mejora_4_e1_plus

# 6. Pull Request en GitHub
# Descripción: qué cambió, testing hecho, impacto en docs
```

---

## 8. Contactos y Referencias

**Autor principal de "mejora_4":**
- **Rama:** `feature/mejora_4_e1_plus` (clonada bajo ALeeSilverAnalytic)
- **Commit push inicial:** Entidad `business-consultant/main` + rebase a feature branch

**Documentación vinculada:**
- [docs/02-design/guia-recuperacion-contexto.md](docs/02-design/guia-recuperacion-contexto.md) — Recuperar estado funcional en minutos
- [docs/02-design/guia-desarrollo.md](docs/02-design/guia-desarrollo.md) — Contribución, arquitectura
- [docs/prompts_hybrid_BESS.md](docs/prompts_hybrid_BESS.md) — Especificación telemetría (68 señales, reglas físicas)

**Punto estable anterior:**
- Commit: `70d2983a62b9e6cd285473c779aac2214c497a52` (2026-06-17)
- Si en algún momento la rama se vuelve inestable, revertir a este punto y reintentar desde ahí

**Útil para debugging:**
- `tests/test_telemetry.py` — Fixture `_bundle()` genera dataset sintético integrado
- `src/bess_simulator/storage/app_config.py` — DEFAULT_ADVANCED_CONFIG documenta 50 parámetros internos
- `src/bess_simulator/ui/app.py:main()` — Entry point; inicio sesión, init_db, routing

---

**Documento finalizado:** 2026-08-28  
**Versión:** 1.0  
**Estado:** Listo para onboarding del siguiente desarrollador en `feature/mejora_4_e1_plus`
