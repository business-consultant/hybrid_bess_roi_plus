# Guía de Desarrollo — BESS Simulator

---

## 0. Recuperación de contexto

Si retomas este proyecto después de días o semanas, usa primero la guía de recuperación:

- `docs/02-design/guia-recuperacion-contexto.md`

Ahí tienes el último commit estable verificado, los comandos para comprobar si hubo cambios posteriores y un prompt listo para poner a Copilot en el punto correcto.

---

## 1. Requisitos del Entorno

| Requisito | Versión |
|-----------|---------|
| Python | ≥ 3.11 |
| pip | Última versión |
| Git | Cualquiera |
| OS | Windows 10/11 (producción), Linux/Mac (desarrollo) |

---

## 2. Instalación para Desarrollo

```bash
git clone <url-del-repo>
cd practica-1

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -e ".[dev]"
```

---

## 3. Ejecución Local

```bash
streamlit run src/bess_simulator/ui/app.py
```

Se abre automáticamente en `http://localhost:8501`.

El tema oscuro y la toolbar mínima se configuran en `.streamlit/config.toml`.

Las páginas están en `ui/views/` (no en `ui/pages/`) para evitar la detección automática de páginas de Streamlit.

---

## 4. Ejecución de Tests

```bash
# Toda la suite
python -m pytest tests/ -v

# Por módulo
python -m pytest tests/test_simulation.py -v
python -m pytest tests/test_synthetic_v2.py -v
python -m pytest tests/test_storage.py -v
```

### Suite de tests actual

| Archivo | Tests | Cobertura |
|---------|-------|-----------|
| `test_simulation.py` | 14 | Motor de cálculo: determinismo (seed=42), propiedades, validación de rangos |
| `test_synthetic_v2.py` | 6 | Datos sintéticos: columnas, SoH decreciente, precios OMIE, continuidad en HOY, flags |
| `test_storage.py` | 13 | Persistencia: init DB, save/load roundtrip, delete, JSON roundtrip |
| **Total** | **33** | |

---

## 5. Estructura de Archivos Clave

```
src/bess_simulator/
├── config.py                        # RANGES, DEFAULTS, DASHBOARD_RANGES, DASHBOARD_DEFAULTS
├── models/
│   ├── parameters.py                # EconomicParams, BessParams, EfficiencyParams, ActivityParams, SimulationInputs
│   └── results.py                   # SimulationResults
├── engine/
│   ├── simulation.py                # run_simulation()
│   ├── sensitivity.py               # run_sensitivity_matrix()
│   └── validation.py
├── recommendations/
│   ├── decision_tree.py             # generate_full_recommendation()
│   ├── sub_recommendations.py
│   └── alarms.py
├── data/
│   ├── synthetic.py                 # generate_dashboard_dataset(), aggregate_to_daily()
│   └── export.py                    # export_simulation_to_excel(), export_dashboard_to_csv()
├── storage/
│   ├── schema.py                    # init_db(), SCHEMA_VERSION
│   ├── repositories.py              # SimulationRepository, DashboardRepository, SensitivityRepository
│   ├── app_config.py                # DEFAULT_ADVANCED_CONFIG, load_config(), save_config(), reset_config()
│   └── paths.py                     # get_db_path(), get_parquet_dir()
└── ui/
    ├── app.py                       # Punto de entrada, navegación, init_db, carga app_config
    ├── views/
    │   ├── simulator.py             # render_simulator_page()
    │   ├── dashboard.py             # render_dashboard_page()
    │   ├── saved_simulations.py     # render_saved_simulations_page()
    │   ├── methodology.py           # render_methodology_page()
    │   └── settings.py              # render_settings_page()
    └── components/
        ├── input_forms.py           # render_input_forms()
        ├── kpi_cards.py             # render_kpi_cards()
        ├── charts.py                # chart_xxx()
        ├── recommendations_panel.py # render_recommendations()
        └── sticky_header.py         # render_sticky_header()
```

---

## 6. Recetas de Extensión

### Agregar un nuevo parámetro de entrada al Simulador

1. Añadir el campo en la dataclass correspondiente en `models/parameters.py`
2. Añadir el rango en `config.py` → `RANGES`
3. Añadir el valor por defecto en `config.py` → `DEFAULTS`
4. Añadir el slider/input en `ui/components/input_forms.py`
5. Añadir la columna en `storage/schema.py` → tabla `simulations`
6. Actualizar `repositories.py` → `save()` y `load_inputs()`
7. Actualizar tests en `test_storage.py`

### Agregar un nuevo parámetro configurable del modelo (advanced_config)

1. Añadir la clave y valor por defecto en `DEFAULT_ADVANCED_CONFIG` en `storage/app_config.py`
2. Añadir el widget correspondiente en `ui/views/settings.py`
3. Consumir el valor con `cfg["clave"]` en el módulo que lo necesite (`simulation.py`, `synthetic.py`, `decision_tree.py`, etc.)
4. Actualizar la página de Metodología si el parámetro es relevante para la documentación

### Agregar un nuevo gráfico

1. Crear la función `chart_xxx()` en `ui/components/charts.py`
2. Importarla en la vista correspondiente (`simulator.py` o `dashboard.py`)
3. Añadirla a una pestaña existente o crear una nueva

### Agregar una nueva página

1. Crear `ui/views/nueva_pagina.py` con función `render_xxx_page()`
2. Añadir la entrada al radio de navegación en `ui/app.py`
3. Añadir la rama `elif` con el import dinámico en `ui/app.py`

### Modificar las estrategias de despacho

Para cambiar cómo se despacha la BESS (carga/descarga por hora), edita los perfiles en `src/bess_simulator/engine/plant.py`:

**Funciones clave**:
1. `_day_power_shape(service, h, rng)` — Arbitraje, Arbitraje+Secundaria, Energy Shifting
2. `_showcase_day_power_shape(h, rng)` — Caso de uso multiservicio (referencia)
3. `_balance_and_scale(power, dt_h, target_discharge)` — Escalado coherente con dataset

**Punto crítico**: Garantizar que `POI[i] = PV[i] + BESS[i] ≤ 50 MW` siempre.

**Estrategia actual** (2026-07-07):
- Curtailment FV duro a `poi_limit_mw` con meseta plana en 50 MW
- Todas las descargas en 20–24h (sin PV)
- Carga nocturna 00–05h
- Modulación suave 12–20h sin exportación positiva

**Para personalizar**:
1. Cambiar ventanas horarias en las funciones `_day_power_shape` y `_showcase_day_power_shape`
2. Mantener el curtailment FV en `build_power_soc_series()` antes de limitar la BESS
3. Validar en tests unitarios que `max(PV) ≤ 50 MW` y `max(POI) ≤ 50 MW`
4. Regenerar histórico en la UI (automático al recargar)

📖 Ver: `docs/02-design/estrategias-despacho.md` (documentación completa)

### Modificar el esquema de base de datos

1. Incrementar `SCHEMA_VERSION` en `storage/schema.py`
2. Añadir SQL de migración en `init_db()`
3. Actualizar los repositorios afectados en `repositories.py`
4. Actualizar los tests en `test_storage.py`

---

## 7. Convenciones

### Código

| Convención | Ejemplo |
|-----------|---------|
| Dataclasses para modelos | `@dataclass class SimulationResults` |
| Type hints en firmas | `def save(self, inputs: SimulationInputs) -> str` |
| Resolución temporal | 15 minutos (`INTERVALS_PER_DAY = 96`) |
| Seeds para reproducibilidad | `seed=42` en tests y botón "Simular" |
| Validación en `__post_init__` | `_check_range(name, value)` contra `config.RANGES` |
| advanced_config | Siempre pasado como argumento, con fallback a `DEFAULT_ADVANCED_CONFIG` |

### Nombrado

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Archivos Python | snake_case | `sensitivity.py` |
| Clases | PascalCase | `SimulationRepository` |
| Funciones | snake_case | `run_simulation()` |
| Constantes | UPPER_SNAKE | `INTERVALS_PER_DAY` |
| Parquet | `{tipo}_{uuid}.parquet` | `sim_a3f2c9b1.parquet` |
| Páginas UI | `render_{nombre}_page()` | `render_simulator_page()` |
| Gráficos | `chart_{nombre}()` | `chart_soh_evolution()` |
| Config dict | `cfg` | `cfg["omie_base_price"]` |

### Git

| Aspecto | Convención |
|---------|-----------|
| Mensajes de commit | `feat:`, `fix:`, `refactor:`, `test:`, `docs:` |
| Branch principal | `master` |
| Datos | Nunca commitear `.db`, `.parquet`, `.csv` (en `.gitignore`) |

---

## 8. Dependencias

### Producción

| Paquete | Versión mín | Propósito |
|---------|-------------|-----------|
| streamlit | 1.30 | UI web |
| pandas | 2.0 | DataFrames |
| numpy | 1.24 | Cálculo vectorizado |
| plotly | 5.18 | Gráficos interactivos |
| openpyxl | 3.1 | Escritura Excel |
| pyarrow | 14.0 | Lectura/escritura Parquet |
| duckdb | 0.10 | Consultas analíticas |

### Desarrollo

| Paquete | Versión mín | Propósito |
|---------|-------------|-----------|
| pytest | 7.4 | Tests |

### Incluidas en stdlib (sin instalar)

| Módulo | Propósito |
|--------|-----------|
| sqlite3 | Base de datos embebida |
| uuid | Generación de identificadores |
| json | Serialización de datos ligeros |
| dataclasses | Modelos de dominio |
| pathlib | Manejo de rutas |
